#!/usr/bin/env python3
"""Exercise the actual MSM KMS ownership of the saved modeset around USB4 sleep.

The USB4 router saves and stops modesetting before it releases DisplayPort for
system sleep and restores it after the router is back. Meanwhile the ordinary
device prepare/complete callbacks must neither take a second snapshot nor
restore early, and atomic commits from other tasks are refused."""
from pathlib import Path
import argparse, re, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True,help='drivers/gpu/drm/msm/msm_kms.c');ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
def extract(name):
 m=re.search(r'(?m)^(int|void|bool) '+name+r'\([^;{}]*\)\s*\{',source);assert m,name
 start=m.start();end=m.end();depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
functions='\n'.join(extract(n) for n in ('msm_kms_usb4_sleep_blocked','msm_kms_usb4_sleep_prepare','msm_kms_usb4_sleep_complete',
 'msm_kms_pm_prepare','msm_kms_pm_complete'))
atomic=(args.source.parent/'msm_atomic.c').read_text()
check=atomic[atomic.index('int msm_atomic_check('):]
assert check.index('if (kms && msm_kms_usb4_sleep_blocked(kms))\n\t\treturn -EBUSY;')<check.index('for_each_oldnew_crtc_in_state')
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
struct task_struct {int id;};
static struct task_struct sleeper={1},compositor={2};static struct task_struct *current=&sleeper;
struct device {void *drvdata;};
struct msm_kms {bool usb4_sleep_owned;struct task_struct *usb4_sleep_task;};
struct drm_mode_config {void *suspend_state;};
struct msm_drm_private;
struct drm_device {struct msm_drm_private *dev_private;struct drm_mode_config mode_config;};
struct msm_drm_private {struct drm_device *dev;struct msm_kms *kms;};
static void *dev_get_drvdata(struct device*d){return d->drvdata;}
static int saves,restores,save_error,commits,refused;static int snapshot;
bool msm_kms_usb4_sleep_blocked(struct msm_kms *kms);
static struct msm_kms kms;
/* A commit attempted from @t while the helper runs (the helper's own commits run as current). */
static void try_commit(struct task_struct*t){struct task_struct*old=current;current=t;if(msm_kms_usb4_sleep_blocked(&kms))refused++;else commits++;current=old;}
static int drm_mode_config_helper_suspend(struct drm_device*d){assert(!d->mode_config.suspend_state);try_commit(current);try_commit(&compositor);
 if(save_error)return save_error;
 saves++;d->mode_config.suspend_state=&snapshot;return 0;}
static int drm_mode_config_helper_resume(struct drm_device*d){assert(d->mode_config.suspend_state);try_commit(current);try_commit(&compositor);
 restores++;d->mode_config.suspend_state=NULL;return 0;}
'''
post=r'''
static struct msm_drm_private priv;static struct drm_device ddev;static struct device dev;static int cases;
static void reset(void){memset(&kms,0,sizeof(kms));memset(&ddev,0,sizeof(ddev));priv.dev=&ddev;priv.kms=&kms;ddev.dev_private=&priv;dev.drvdata=&priv;
 saves=restores=save_error=commits=refused=0;current=&sleeper;}
static bool blocked(struct task_struct*t){struct task_struct*old=current;current=t;bool b=msm_kms_usb4_sleep_blocked(&kms);current=old;return b;}
int main(void){
 /* USB4 sleep: one snapshot by the owner; its own helper commits pass, others are refused. */
 reset();assert(!msm_kms_usb4_sleep_prepare(&ddev));assert(saves==1&&kms.usb4_sleep_owned&&!kms.usb4_sleep_task&&commits==1&&refused==1);
 /* Until restore every task is refused, the sleep service included. */
 assert(blocked(&sleeper)&&blocked(&compositor));
 /* Device callbacks during the same sleep leave the saved state alone. */
 assert(!msm_kms_pm_prepare(&dev));msm_kms_pm_complete(&dev);assert(saves==1&&!restores&&ddev.mode_config.suspend_state);
 /* Restore after the router is back; the owner's commits pass again during it. */
 commits=refused=0;assert(!msm_kms_usb4_sleep_complete(&ddev));
 assert(restores==1&&!kms.usb4_sleep_owned&&!kms.usb4_sleep_task&&commits==1&&refused==1&&!blocked(&compositor));cases++;
 /* Without USB4 the ordinary callbacks suspend and resume as upstream. */
 reset();assert(!msm_kms_pm_prepare(&dev));msm_kms_pm_complete(&dev);assert(saves==1&&restores==1);cases++;
 /* A failed save releases ownership. */
 reset();save_error=-EIO;assert(msm_kms_usb4_sleep_prepare(&ddev)==-EIO);assert(!kms.usb4_sleep_owned&&!blocked(&compositor));cases++;
 /* A second prepare, or one after the ordinary snapshot, is refused. */
 reset();assert(!msm_kms_usb4_sleep_prepare(&ddev));assert(msm_kms_usb4_sleep_prepare(&ddev)==-EBUSY&&saves==1);cases++;
 reset();assert(!msm_kms_pm_prepare(&dev));assert(msm_kms_usb4_sleep_prepare(&ddev)==-EBUSY&&!kms.usb4_sleep_owned);cases++;
 /* Complete without a USB4 snapshot does nothing. */
 reset();assert(!msm_kms_usb4_sleep_complete(&ddev));assert(!restores);cases++;
 /* No KMS. */
 reset();priv.kms=NULL;assert(msm_kms_usb4_sleep_prepare(&ddev)==-ENODEV);assert(!msm_kms_usb4_sleep_complete(&ddev));assert(!msm_kms_pm_prepare(&dev));cases++;
 printf("PASS %d extracted MSM KMS USB4 sleep cases\n",cases);
}
'''
FLAGS=['-Wall','-Werror','-Wno-unused-function']
MUTATIONS=[
 ('device_prepare_snapshots_again','\tif (!priv || !priv->kms)\n\t\treturn 0;\n\tif (priv->kms->usb4_sleep_owned)\n\t\treturn 0;\n\n\treturn drm_mode_config_helper_suspend(ddev);','\tif (!priv || !priv->kms)\n\t\treturn 0;\n\n\treturn drm_mode_config_helper_suspend(ddev);'),
 ('device_complete_restores_early','\tif (priv->kms->usb4_sleep_owned)\n\t\treturn;\n',''),
 ('owner_never_released','\tret = drm_mode_config_helper_resume(ddev);\n\tWRITE_ONCE(priv->kms->usb4_sleep_owned, false);','\tret = drm_mode_config_helper_resume(ddev);'),
 ('owner_task_refused','return READ_ONCE(kms->usb4_sleep_owned) &&\n\t       READ_ONCE(kms->usb4_sleep_task) != current;','return READ_ONCE(kms->usb4_sleep_owned);'),
 ('failed_save_keeps_owner','\tif (ret)\n\t\tWRITE_ONCE(priv->kms->usb4_sleep_owned, false);\n',''),
]
variants={'correct':functions}
for name,old,new in MUTATIONS:
 assert functions.count(old)==1,name
 variants[name]=functions.replace(old,new)
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp);results={}
 for name,body in variants.items():
  c=d/(name+'.c');exe=d/name;c.write_text(header+body+post)
  flags=FLAGS if name=='correct' else ['-w']
  subprocess.run(['cc','-include',HARNESS_HEADER,'-std=gnu11',*flags,'-fsanitize=address,undefined','-g',str(c),'-o',str(exe)],check=True)
  r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
  if name=='correct':assert r.returncode==0,r.stderr;print(r.stdout.strip());results[name]='pass'
  else:assert body!=functions and r.returncode==134,(name,r.returncode,r.stderr[-300:]);results[name]='rejected'
 if args.output:args.output.write_text(json.dumps({'variants':results},indent=2)+'\n')
 print(results)
