#!/usr/bin/env python3
"""Exercise the actual USB4 DisplayPort provider sleep calls: save the modeset
before the router sleeps or stops, rediscover DP after a kept router resumes,
and restore the modeset afterwards, waiting for the tunnel only if a sink was
driven through it before sleep."""
from pathlib import Path
import argparse, re, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True,help='drivers/thunderbolt/qcom-usb4-dp.c');ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
def extract(name):
 m=re.search(r'(?m)^int '+name+r'\([^;{}]*\)\s*\{',source);assert m,name
 start=m.start();end=m.end();depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
functions='\n'.join(extract(n) for n in ('qcom_usb4_dp_sleep_prepare','qcom_usb4_dp_resume_discover','qcom_usb4_dp_sleep_complete'))
ready_ms=re.search(r'(?m)^#define DP_SLEEP_READY_MS\s+(\d+)$',source);assert ready_ms and ready_ms[1]=='15000'
# Discovery and lifecycle work stay quiet while a kept router sleeps (1.138, clean in 1.142).
assert 'if (release && !ret && !READ_ONCE(dp->stopping) && !READ_ONCE(dp->sleeping))' in source
assert "} else if (READ_ONCE(dp->enabled) && !READ_ONCE(dp->allocated) &&\n\t\t\t   !READ_ONCE(dp->sleeping)) {" in source
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define DP_SLEEP_READY_MS '''+ready_ms[1]+r'''
struct mutex {int held;};
struct device {int refs;};
struct delayed_work {int queued;};
typedef struct {int unused;} wait_queue_head_t;
struct qcom_usb4_dp {struct device *dev;struct device *display;struct device *sleep_display;bool sleep_had_sink;wait_queue_head_t ready_wait;
 bool connected;bool sleeping;struct mutex lifecycle_lock;struct mutex state_lock;struct delayed_work mailbox_work;bool enabled;bool allocated;bool ready;};
static void *system_unbound_wq;
static int discovers,saves,save_error,restores,hpd_syncs,errors;static long now,ready_at,gone_at;
static void mutex_lock(struct mutex*m){assert(!m->held);m->held=1;}
static void mutex_unlock(struct mutex*m){assert(m->held);m->held=0;}
static struct device *get_device(struct device*d){d->refs++;return d;}
static void put_device(struct device*d){assert(d->refs>0);d->refs--;}
static long msecs_to_jiffies(long ms){return ms;}
#define dev_err(...) (errors++)
static bool queue_delayed_work(void*wq,struct delayed_work*w,long d){(void)wq;(void)d;w->queued=1;return true;}
static int dp_discover(struct qcom_usb4_dp*dp){assert(dp->lifecycle_lock.held&&dp->mailbox_work.queued);discovers++;return 0;}
static int msm_dp_usb4_sleep_prepare(struct device*d){(void)d;if(save_error)return save_error;saves++;return 0;}
static int msm_dp_usb4_sleep_complete(struct device*d){(void)d;restores++;return 0;}
static int msm_dp_usb4_hpd_sync(struct device*d,bool c,bool irq){(void)d;assert(c&&!irq);hpd_syncs++;return 0;}
/* Time passes 1 ms per wait step; the tunnel becomes ready (or the partner goes) at a scheduled time. */
static struct qcom_usb4_dp gdp;
static void tick(void){now++;if(ready_at>=0&&now>=ready_at){gdp.ready=true;gdp.allocated=true;}if(gone_at>=0&&now>=gone_at)gdp.connected=false;}
#define wait_event_timeout(wq,cond,timeout) ({long __t=(timeout),__r;assert(!gdp.lifecycle_lock.held);\
 for(;;){if(cond){__r=__t>0?__t:1;break;}if(__t<=0){__r=0;break;}tick();__t--;}__r;})
'''
post=r'''
#define dp gdp
static struct device display,provider;static int cases;
static void reset(bool sink){memset(&dp,0,sizeof(dp));display.refs=1;dp.dev=&provider;dp.display=&display;dp.enabled=true;dp.connected=true;
 dp.allocated=sink;dp.ready=sink;discovers=saves=save_error=restores=hpd_syncs=errors=0;now=0;ready_at=gone_at=-1;}
/* Sleep: the router stops or sleeps and the tunnel goes away; after resume it may come back. */
static void sleep_and_wake(long back_at){dp.ready=false;dp.allocated=false;ready_at=back_at;}
int main(void){
 /* Dell driven before sleep: wait for the tunnel, resync HPD, then restore. */
 reset(true);assert(!qcom_usb4_dp_sleep_prepare(&dp));assert(saves==1&&dp.sleep_display==&display&&display.refs==2&&dp.sleeping&&dp.sleep_had_sink);
 sleep_and_wake(1200);assert(!qcom_usb4_dp_sleep_complete(&dp,true));
 assert(now==1200&&hpd_syncs==1&&restores==1&&!dp.sleep_display&&display.refs==1&&!dp.sleeping&&!errors);cases++;
 /* Dock without a monitor: no sink, so no wait; the internal panel comes back at once. */
 reset(false);assert(!qcom_usb4_dp_sleep_prepare(&dp));assert(!dp.sleep_had_sink);sleep_and_wake(-1);
 assert(!qcom_usb4_dp_sleep_complete(&dp,true));assert(now==0&&!hpd_syncs&&restores==1&&!errors);cases++;
 /* A monitor attached during sleep is left to hotplug. */
 reset(false);assert(!qcom_usb4_dp_sleep_prepare(&dp));sleep_and_wake(300);assert(!qcom_usb4_dp_sleep_complete(&dp,true));assert(now==0&&!hpd_syncs&&restores==1);cases++;
 /* Partner gone after resume: no wait, restore. */
 reset(true);assert(!qcom_usb4_dp_sleep_prepare(&dp));sleep_and_wake(-1);dp.connected=false;
 assert(!qcom_usb4_dp_sleep_complete(&dp,false));assert(now==0&&!hpd_syncs&&restores==1);cases++;
 /* Partner leaves while we wait: stop waiting, report it, still restore. */
 reset(true);assert(!qcom_usb4_dp_sleep_prepare(&dp));sleep_and_wake(-1);gone_at=400;
 assert(qcom_usb4_dp_sleep_complete(&dp,true)==-ENODEV);assert(now==400&&!hpd_syncs&&restores==1&&errors==1);cases++;
 /* The tunnel never returns: give up after the bound, still restore. */
 reset(true);assert(!qcom_usb4_dp_sleep_prepare(&dp));sleep_and_wake(-1);
 assert(qcom_usb4_dp_sleep_complete(&dp,true)==-ETIMEDOUT);assert(now==DP_SLEEP_READY_MS&&restores==1&&errors==1&&!dp.sleep_display);cases++;
 /* No DP owner: nothing is saved or restored. */
 reset(true);dp.enabled=false;assert(!qcom_usb4_dp_sleep_prepare(&dp));assert(!saves&&!dp.sleep_display);
 assert(!qcom_usb4_dp_sleep_complete(&dp,true));assert(!restores);cases++;
 /* A second prepare before complete is refused; a failed save leaves nothing to restore. */
 reset(true);assert(!qcom_usb4_dp_sleep_prepare(&dp));assert(qcom_usb4_dp_sleep_prepare(&dp)==-EBUSY&&saves==1);cases++;
 reset(true);save_error=-EIO;assert(qcom_usb4_dp_sleep_prepare(&dp)==-EIO);assert(!dp.sleep_display&&display.refs==1);
 assert(!qcom_usb4_dp_sleep_complete(&dp,true));assert(!restores&&!dp.sleeping);cases++;
 /* Kept router resumed: rediscover DP once, unless a tunnel is already allocated. */
 reset(false);assert(!qcom_usb4_dp_sleep_prepare(&dp));assert(!qcom_usb4_dp_resume_discover(&dp));assert(discovers==1&&!dp.sleeping);cases++;
 reset(true);assert(!qcom_usb4_dp_sleep_prepare(&dp));assert(!qcom_usb4_dp_resume_discover(&dp));assert(!discovers&&!dp.sleeping);cases++;
 reset(false);dp.connected=false;assert(!qcom_usb4_dp_resume_discover(&dp));assert(!discovers);cases++;
 printf("PASS %d extracted DP provider sleep cases\n",cases);
}
'''
FLAGS=['-Wall','-Werror','-Wno-unused-function']
MUTATIONS=[
 ('wait_without_sink','\tconnected = connected && dp->sleep_had_sink;\n',''),
 ('sink_not_recorded','\tdp->sleep_had_sink = dp->ready;\n',''),
 ('restore_skipped_on_failure','\tret = msm_dp_usb4_sleep_complete(display);','\tret = ready_ret ? 0 : msm_dp_usb4_sleep_complete(display);'),
 ('discover_when_allocated','if (dp->enabled && READ_ONCE(dp->connected) && !dp->allocated) {','if (dp->enabled && READ_ONCE(dp->connected)) {'),
 ('sleeping_kept_after_discover','\tmutex_lock(&dp->lifecycle_lock);\n\tWRITE_ONCE(dp->sleeping, false);\n','\tmutex_lock(&dp->lifecycle_lock);\n'),
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
  r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60)
  if name=='correct':assert r.returncode==0,r.stderr;print(r.stdout.strip());results[name]='pass'
  else:assert body!=functions and r.returncode==134,(name,r.returncode,r.stderr[-300:]);results[name]='rejected'
 if args.output:args.output.write_text(json.dumps({'variants':results},indent=2)+'\n')
 print(results)
