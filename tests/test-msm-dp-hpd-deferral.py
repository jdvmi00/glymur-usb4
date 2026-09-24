#!/usr/bin/env python3
"""Exercise the actual msm DP HPD notify/work/detect code against the recorded Type-C boot replay."""
from pathlib import Path
import argparse, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True,help='drivers/gpu/drm/msm/dp/dp_display.c');ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
import re
def extract(name,prefix='static '):
 m=[m for m in re.finditer(r'(?m)^[a-z][^;\n]*\b'+name+r'\([^;]*?\)\s*\{',source)]
 assert len(m)==1,(name,len(m))
 start=m[0].start(); brace=source.index('{',m[0].start());end=brace+1;depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
functions='\n'.join([extract('msm_dp_display_hpd_gone'),extract('msm_dp_hpd_plug_handle'),
 extract('msm_dp_bridge_detect','enum drm_connector_status '),extract('msm_dp_hpd_work'),extract('msm_dp_bridge_hpd_notify','void ')])
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef uint32_t u32;
#define container_of(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define smp_mb() ((void)0)
#define DP_RECEIVER_CAP_SIZE 16
#define ISR_HPD_REPLUG_COUNT 3
#define ISR_IRQ_HPD_PULSE_COUNT 4
enum drm_connector_status {connector_status_connected=1,connector_status_disconnected=2,connector_status_unknown=3};
struct task_struct {int id;};
static struct task_struct altmode_task={1},fbdev_task={2},hpd_worker={3},*current=&altmode_task;
struct mutex {int held;};
struct guard_mutex {struct mutex *m;};
static void guard_unlock(struct guard_mutex *g){assert(g->m->held);g->m->held=0;}
static struct guard_mutex guard_lock(struct mutex*m){assert(!m->held);m->held=1;return (struct guard_mutex){m};}
#define guard(t) struct guard_mutex __attribute__((cleanup(guard_unlock))) _g = guard_lock
struct work_struct {int queued;};
struct device {int unused;};
struct platform_device {struct device dev;};
struct drm_device {int unused;};
struct drm_connector {int unused;};
struct drm_dp_aux {int unused;};
struct drm_dp_desc {int unused;};
struct msm_dp_link {int sink_count;};
struct msm_dp {struct platform_device *pdev;int connector_type;};
struct drm_bridge {int unused;};
struct msm_dp_bridge {struct drm_bridge bridge;struct msm_dp *msm_dp_display;};
#define to_dp_bridge(b) container_of(b,struct msm_dp_bridge,bridge)
struct msm_dp_display_private {
 struct msm_dp msm_dp_display;struct drm_device *drm_dev;struct msm_dp_link *link;struct drm_dp_aux *aux;
 struct mutex plugged_lock;bool plugged;
 struct work_struct hpd_work;enum drm_connector_status hpd_status;enum drm_connector_status work_status;struct task_struct *detect_task;
};
#define drm_dbg_dp(...) ((void)0)
#define DRM_DEBUG_DP(...) ((void)0)
#define DRM_ERROR(...) ((void)0)
/* Simulated AUX: timeouts cost 8 s per DPCD read (32 x 250 ms), refusals 16 ms. */
static double clock_s; static bool xfers, sink_answers, usb4_attached; static int reads, reads_in_notify, hotplug_events, plugs, unplugs, rpm;
static bool in_notify; static void (*mid_read_hook)(void);
static void *system_long_wq;
static bool queue_work(void*wq,struct work_struct*w){(void)wq;w->queued=1;return true;}
static int pm_runtime_resume_and_get(struct device*d){(void)d;rpm++;return 0;}
static void pm_runtime_put_sync(struct device*d){(void)d;rpm--;}
static void msm_dp_aux_enable_xfers(struct drm_dp_aux*a,bool e){(void)a;xfers=e;}
static bool msm_dp_aux_usb4_attached(struct drm_dp_aux*a){(void)a;return usb4_attached;}
static u32 msm_dp_aux_is_link_connected(struct drm_dp_aux*a){(void)a;return 0;}
static bool msm_dp_aux_link_plugged(struct drm_dp_aux*a){(void)a;return true;}
static int dpcd_read(void){
 reads++; if(in_notify) reads_in_notify++;
 if(mid_read_hook){void(*h)(void)=mid_read_hook;mid_read_hook=NULL;h();}
 if(!xfers){clock_s+=0.016;return -ENXIO;}
 if(!sink_answers){clock_s+=8.0;return -ETIMEDOUT;}
 clock_s+=0.001;return 0;}
static struct msm_dp_display_private *active;
static void (*phy_init_hook)(void);
static int msm_dp_display_host_phy_init(struct msm_dp_display_private*dp){(void)dp;if(phy_init_hook){void(*h)(void)=phy_init_hook;phy_init_hook=NULL;h();}return 1;}
static void msm_dp_display_host_phy_exit(struct msm_dp_display_private*dp){(void)dp;}
static int msm_dp_display_process_hpd_high(struct msm_dp_display_private*dp){int r=dpcd_read();if(!r){r=dpcd_read();if(!r)dp->link->sink_count=1;}return r;}
static int msm_dp_hpd_unplug_handle(struct msm_dp_display_private*dp){guard(mutex)(&dp->plugged_lock);unplugs++;if(dp->plugged){pm_runtime_put_sync(&dp->msm_dp_display.pdev->dev);dp->plugged=false;}dp->link->sink_count=0;xfers=false;return 0;}
static int msm_dp_irq_hpd_handle(struct msm_dp_display_private*dp){(void)dp;return 0;}
static int drm_dp_read_dpcd_caps(struct drm_dp_aux*a,u8*d){(void)a;(void)d;return dpcd_read();}
static int drm_dp_read_desc(struct drm_dp_aux*a,struct drm_dp_desc*d,bool b){(void)a;(void)d;(void)b;return dpcd_read();}
static bool drm_dp_is_branch(const u8*d){(void)d;return false;}
static bool drm_dp_read_sink_count_cap(struct drm_connector*c,const u8*d,const struct drm_dp_desc*e){(void)c;(void)d;(void)e;return false;}
static int drm_dp_read_sink_count(struct drm_dp_aux*a){(void)a;return 1;}
static void drm_kms_helper_hotplug_event(struct drm_device*d){(void)d;hotplug_events++;}
static int msm_dp_hpd_plug_handle(struct msm_dp_display_private *dp);
'''
post=r'''
static struct platform_device pdev; static struct drm_device drm; static struct msm_dp_link link; static struct drm_dp_aux aux;
static struct msm_dp_display_private dp; static struct msm_dp_bridge br; static struct drm_connector conn; static int cases;
static void reset(void){memset(&dp,0,sizeof(dp));dp.msm_dp_display.pdev=&pdev;dp.drm_dev=&drm;dp.link=&link;dp.aux=&aux;link.sink_count=0;
 dp.hpd_status=dp.work_status=connector_status_unknown;br.msm_dp_display=&dp.msm_dp_display;active=&dp;
 clock_s=0;xfers=false;sink_answers=true;usb4_attached=false;reads=reads_in_notify=hotplug_events=plugs=unplugs=rpm=0;mid_read_hook=NULL;phy_init_hook=NULL;}
static void notify(struct task_struct*t,enum drm_connector_status s){struct task_struct*o=current;current=t;in_notify=true;msm_dp_bridge_hpd_notify(&br.bridge,&conn,s);in_notify=false;current=o;}  /* may run while the HPD worker holds plugged_lock */
static void work(void){if(!dp.hpd_work.queued)return;dp.hpd_work.queued=0;struct task_struct*o=current;current=&hpd_worker;msm_dp_hpd_work((struct work_struct*)&dp.hpd_work);current=o;assert(!dp.plugged_lock.held);}
/* The bridge connector's detect: detect(), then hpd_notify() with its result. */
static enum drm_connector_status probe(struct task_struct*t){struct task_struct*o=current;current=t;enum drm_connector_status s=msm_dp_bridge_detect(&br.bridge,&conn);in_notify=true;msm_dp_bridge_hpd_notify(&br.bridge,&conn,s);in_notify=false;current=o;return s;}
static void withdraw(void){notify(&altmode_task,connector_status_disconnected);}
int main(void){
 /* Recorded boot replay: stale DP pin D with HPD, then the safe state 1 ms later; the Dell never answers native AUX. */
 reset();sink_answers=false;notify(&altmode_task,connector_status_connected);
 assert(!reads_in_notify&&dp.hpd_work.queued);            /* the altmode worker is free at once */
 mid_read_hook=withdraw;work();                            /* safe state arrives during the first read */
 assert(dp.hpd_status==connector_status_disconnected&&!xfers);
 work();assert(!dp.plugged&&unplugs==1);
 assert(clock_s<1.0);                                      /* was ~16 s blocking the notifier */
 double t=clock_s;int r=reads;
 assert(probe(&fbdev_task)==connector_status_disconnected&&reads==r&&clock_s==t); /* fbdev probe needs no AUX */
 assert(dp.hpd_status==connector_status_disconnected);cases++;
 /* While the worker holds plugged_lock, a detect for a withdrawn sink must not wait for it. */
 dp.plugged_lock.held=1;assert(probe(&fbdev_task)==connector_status_disconnected);dp.plugged_lock.held=0;cases++;
 /* The safe state lands between the worker's check and its enabling of transfers. */
 reset();sink_answers=false;notify(&altmode_task,connector_status_connected);phy_init_hook=withdraw;work();
 assert(!xfers&&clock_s<1.0);work();assert(!dp.plugged);cases++;
 /* The safe state lands while detect powers the PHY: detect sends nothing afterwards. */
 reset();notify(&altmode_task,connector_status_connected);work();assert(dp.plugged);sink_answers=false;
 phy_init_hook=withdraw;double c0=clock_s;assert(probe(&fbdev_task)==connector_status_disconnected&&clock_s-c0<0.1);cases++;
 /* The same replay with the safe state queued before the work starts. */
 reset();sink_answers=false;notify(&altmode_task,connector_status_connected);withdraw();work();
 assert(!xfers&&clock_s<1.0&&!dp.plugged);cases++;
 /* A genuine plug: HPD high and a sink that answers. */
 reset();notify(&altmode_task,connector_status_connected);work();
 assert(dp.plugged&&link.sink_count==1&&xfers&&hotplug_events==1&&!reads_in_notify);
 /* detect's echo re-runs the work without another hotplug event: no event loop. */
 for(int i=0;i<5;i++){assert(probe(&fbdev_task)==connector_status_connected);work();}
 assert(hotplug_events==1&&dp.hpd_status==connector_status_connected);cases++;
 /* A detect read failure while HPD stays high is an echo: it must not mark the sink gone. */
 sink_answers=false;assert(probe(&fbdev_task)==connector_status_disconnected);
 assert(dp.hpd_status==connector_status_connected&&dp.detect_task==NULL);
 work();sink_answers=true;
 /* The next HPD report from the port (e.g. IRQ_HPD) is not suppressed and replugs. */
 r=reads;notify(&altmode_task,connector_status_connected);work();assert(reads>r&&dp.plugged&&xfers);cases++;
 /* Physical unplug through the HPD source. */
 int h=hotplug_events;withdraw();assert(!xfers);work();assert(!dp.plugged&&hotplug_events==h+1);cases++;
 /* A USB4 tunnel owns HPD: notifications are ignored, and a withdrawn native HPD does not block its plug. */
 reset();withdraw();work();usb4_attached=true;notify(&altmode_task,connector_status_connected);assert(!dp.hpd_work.queued);
 assert(!msm_dp_display_hpd_gone(&dp));msm_dp_hpd_plug_handle(&dp);assert(xfers);cases++;
 /* Without any HPD report (unknown status) a plugged sink is detected over AUX as upstream. */
 reset();dp.plugged=true;r=reads;assert(probe(&fbdev_task)==connector_status_connected&&reads>r);cases++;
 printf("PASS %d extracted msm DP HPD deferral sequences\n",cases);
}
'''
FLAGS=['-Wall', '-Werror', '-Wno-unused-function', '-Wno-unused-variable']
MUTATIONS=[
 ('notify_waits_for_aux','queue_work(system_long_wq, &dp->hpd_work);','msm_dp_hpd_work(&dp->hpd_work);'),
 ('withdraw_keeps_transfers','smp_mb();\n\t\t\tmsm_dp_aux_enable_xfers(dp->aux, false);','smp_mb();'),
 ('plug_no_recheck','smp_mb();\n\tif (msm_dp_display_hpd_gone(dp))\n\t\tmsm_dp_aux_enable_xfers(dp->aux, false);','smp_mb();'),
 ('detect_ignores_withdrawn_hpd','if (msm_dp_display_hpd_gone(priv))\n\t\treturn status;',''),
 ('detect_no_recheck','if (msm_dp_display_hpd_gone(priv)) {','if (0) {'),
 ('detect_echo_marks_gone','if (READ_ONCE(dp->detect_task) == current) {','if (0) {'),
 ('detect_not_marked','WRITE_ONCE(priv->detect_task, current);',';'),
 ('hotplug_event_every_run','if (READ_ONCE(dp->plugged) != was_plugged || dp->link->sink_count != sink_count)','if (1)'),
 ('usb4_hpd_blocks_plug',' &&\n\t       !msm_dp_aux_usb4_attached(dp->aux);',';'),
 ('usb4_notify_processed','if (msm_dp_aux_usb4_attached(dp->aux))\n\t\treturn;\n\n\t/*\n\t * Record','/*\n\t * Record'),
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
  else:assert body!=functions and r.returncode==134,(name,r.returncode);results[name]='rejected'
 if args.output:args.output.write_text(json.dumps({'variants':results},indent=2)+'\n')
 print(results)
