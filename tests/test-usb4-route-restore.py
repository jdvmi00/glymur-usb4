#!/usr/bin/env python3
"""Exercise extracted DPU routing across simulated register power loss and system sleep.

The route is programmed only into an active DPU; otherwise (runtime suspended,
or runtime PM disabled in the late system-sleep phase) it is cached and the
DPU runtime resume restores it."""
from pathlib import Path
import argparse,json,subprocess,tempfile
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
p=argparse.ArgumentParser();p.add_argument('--source-dir',required=True,type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
s=(a.source_dir/'dpu_kms.c').read_text();start=s.index('static void dpu_kms_restore_usb4_dp_route(');end=s.index('static const struct msm_kms_funcs',start);funcs=s[start:end]
s=(a.source_dir/'dpu_hw_top.c').read_text();start=s.index('#define MDP_DP_USB4_MUX ');end=s.index('static void dpu_hw_setup_split_pipe(',start);hw=s[start:end]
pre=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
struct mutex {int held;};
struct device {void *of_node;};
struct platform_device {struct device dev;};
struct msm_kms {int unused;};
struct dpu_hw_blk_reg_map {int unused;};
struct dpu_hw_mdp {struct dpu_hw_blk_reg_map hw;};
struct dpu_kms {struct msm_kms base;struct platform_device *pdev;struct dpu_hw_mdp *hw_mdp;struct mutex usb4_route_lock;u32 usb4_dp_route;bool usb4_dp_route_valid;};
#define to_dpu_kms(k) ((struct dpu_kms*)((char*)(k)-offsetof(struct dpu_kms,base)))
#define dev_info(...) ((void)0)
static struct dpu_kms *active;
static bool compatible;
static int refs,rpm_disabled,pm_gets,pm_puts,reg_reads,reg_writes;
static u32 reg;
static void mutex_lock(struct mutex*m){assert(!m->held);m->held=1;}
static void mutex_unlock(struct mutex*m){assert(m->held);m->held=0;}
static bool of_device_is_compatible(void*n,const char*s){(void)n;assert(!strcmp(s,"qcom,glymur-dpu"));return compatible;}
static u32 reg_read(struct dpu_hw_blk_reg_map*c,unsigned off){assert(refs>0&&c==&active->hw_mdp->hw&&off==0x464);reg_reads++;return reg;}
static void reg_write(struct dpu_hw_blk_reg_map*c,unsigned off,u32 v){assert(refs>0&&c==&active->hw_mdp->hw&&off==0x464);reg_writes++;reg=v;}
#define DPU_REG_READ(c,o) reg_read(c,o)
#define DPU_REG_WRITE(c,o,v) reg_write(c,o,v)
static void dpu_kms_restore_usb4_dp_route(struct dpu_kms *);
/* Runtime PM model: registers are lost when the last reference goes; resume
 * restores the cached route. Disabled runtime PM (late system sleep) refuses
 * conditional references and resumes, as the PM core does. */
static void resume_dpu(void){assert(!rpm_disabled);if(refs++==0){reg=0;dpu_kms_restore_usb4_dp_route(active);}}
static void suspend_dpu(void){assert(refs>0);if(--refs==0)reg=0;}
static int pm_runtime_get_if_active(struct device*d){
 assert(d==&active->pdev->dev&&!active->usb4_route_lock.held);pm_gets++;
 if(rpm_disabled)return -EINVAL;
 if(!refs)return 0;
 refs++;return 1;
}
static void pm_runtime_put(struct device*d){assert(d==&active->pdev->dev&&refs>0&&!active->usb4_route_lock.held);pm_puts++;suspend_dpu();}
/* The 1.89 behavior, for the negative control that restores it. */
__attribute__((unused)) static int pm_runtime_resume_and_get(struct device*d){
 assert(d==&active->pdev->dev&&!active->usb4_route_lock.held);pm_gets++;
 if(rpm_disabled)return -EACCES;
 resume_dpu();return 0;
}
'''
post=r'''
int main(void){
 struct platform_device pdev={0};struct dpu_hw_mdp mdp={0};struct dpu_kms kms={.pdev=&pdev,.hw_mdp=&mdp};active=&kms;int cases=0;
 /* state 0: runtime suspended; 1: active; 2: active with runtime PM disabled
  * (late system sleep); 3: suspended with runtime PM disabled. */
 for(int state=0;state<4;state++)for(unsigned previous=0;previous<4;previous++)for(unsigned resource=0;resource<4;resource++){
  bool powered=state==1||state==2;
  refs=powered;rpm_disabled=state>=2;reg=powered?0xa5a50000U|previous:0;compatible=true;pm_gets=pm_puts=reg_reads=reg_writes=0;kms.usb4_dp_route=previous;kms.usb4_dp_route_valid=true;
  int ret=dpu_kms_set_usb4_dp_route(&kms.base,resource);
  assert(!ret&&refs==powered&&pm_gets==1&&!kms.usb4_route_lock.held);
  assert(kms.usb4_dp_route==resource&&kms.usb4_dp_route_valid);
  if(state==1){assert(pm_puts==1&&reg_writes==1&&reg==(0xa5a50000U|resource));}
  else{assert(!pm_puts&&!reg_reads&&!reg_writes&&reg==(powered?0xa5a50000U|previous:0));}
  /* Runtime PM back on, registers lost, then resume repeatedly with the cached route. */
  rpm_disabled=0;if(powered)suspend_dpu();
  for(int cycle=0;cycle<4;cycle++){assert(!refs&&!reg);resume_dpu();assert(reg==resource);suspend_dpu();}
  assert(!refs&&!reg&&!kms.usb4_route_lock.held);
  cases++;
 }
 /* Unsupported hardware and invalid resources never touch PM or registers. */
 for(int invalid=0;invalid<3;invalid++){
  refs=0;rpm_disabled=0;compatible=invalid!=0;kms.hw_mdp=invalid==1?NULL:&mdp;pm_gets=pm_puts=reg_reads=reg_writes=0;
  int ret=dpu_kms_set_usb4_dp_route(&kms.base,invalid==2?4:1);
  assert(ret==(invalid==2?-EINVAL:-EOPNOTSUPP));assert(!pm_gets&&!pm_puts&&!reg_reads&&!reg_writes);cases++;
 }
 /* Early probe / no USB4 use must not access hardware. */
 kms.hw_mdp=NULL;kms.usb4_dp_route_valid=false;reg_reads=reg_writes=0;dpu_kms_restore_usb4_dp_route(&kms);assert(!reg_reads&&!reg_writes);cases++;
 printf("PASS %d extracted DPU route/restore cases\n",cases);
}
'''
# Confirm the real resume callback calls restoration after clocks and before encoders.
s=(a.source_dir/'dpu_kms.c').read_text();r=s[s.index('static int __maybe_unused dpu_runtime_resume('):]
assert r.index('clk_bulk_prepare_enable')<r.index('dpu_kms_restore_usb4_dp_route(dpu_kms)')<r.index('drm_for_each_encoder')
assert 'mutex_init(&dpu_kms->usb4_route_lock)' in s
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp);c=d/'route.c';exe=d/'route';c.write_text(pre+hw+funcs+post)
 subprocess.run(['cc','-include',HARNESS_HEADER,'-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe)],capture_output=True,text=True,check=True);print(r.stdout,end='');cases=int(r.stdout.split()[1])
 mutants={'no_resume_restore':funcs.replace('dpu_hw_setup_usb4_dp_route(dpu_kms->hw_mdp, dpu_kms->usb4_dp_route);',';'),
  'stale_cached_route':funcs.replace('dpu_kms->usb4_dp_route = resource;','dpu_kms->usb4_dp_route = 0;'),
  'leaked_power_reference':funcs.replace('pm_runtime_put(dev);',';'),
  'programs_inactive_dpu':funcs.replace('\tif (ret > 0)\n\t\tdpu_hw_setup_usb4_dp_route(dpu_kms->hw_mdp, resource);','\tdpu_hw_setup_usb4_dp_route(dpu_kms->hw_mdp, resource);'),
  'resumes_dpu_in_sleep':funcs.replace('ret = pm_runtime_get_if_active(dev);','ret = pm_runtime_resume_and_get(dev);\n\tif (ret < 0)\n\t\treturn ret;\n\tret = 1;')}
 results={}
 for name,fn in mutants.items():
  assert fn!=funcs;c.write_text(pre+hw+fn+post);subprocess.run(['cc','-include',HARNESS_HEADER,'-std=gnu11','-w',str(c),'-o',str(exe)],check=True)
  r=subprocess.run([str(exe)],capture_output=True,text=True);assert r.returncode==134,name;results[name]='rejected'
 result={'extracted_cases':cases,'ASan_UBSan':'pass','negative_controls':results,'scope':'Active, runtime-suspended and sleep-disabled DPU, cached routing across register loss, unsupported hardware; no concurrency; requires hardware validation'}
 if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
