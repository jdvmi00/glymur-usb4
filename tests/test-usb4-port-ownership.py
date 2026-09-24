#!/usr/bin/env python3
"""Exercise the actual router port-ownership decisions against recorded Type-C sequences."""
from pathlib import Path
import argparse, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True,help='drivers/thunderbolt/qcom-usb4-host.c');ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
def extract(name):
 start=source.rfind('static ',0,source.index(name+'(')); brace=source.index('{',start);end=brace+1;depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
functions='\n'.join(extract(n) for n in ('qcom_usb4_host_apply_link','qcom_usb4_host_mux_set','qcom_usb4_host_lifecycle_work'))
assert 'QCOM_USB4_IDLE_STOP_MS\t\t500' in source
# Probe no longer starts the router; it only becomes ready.
probe=source[source.index('static int qcom_usb4_host_probe('):source.index('static void qcom_usb4_host_teardown(')]
assert 'qcom_usb4_host_start(' not in probe and 'host->released = true;' in probe
# A USB4 entry reported before the router became ready starts it right away.
assert 'host->released = true;\n\tif (host->pending == QCOM_USB4_LINK_CONNECT)\n\t\tmod_delayed_work(system_long_wq, &host->lifecycle_work, 0);' in probe
assert '.suppress_bind_attrs = true' in source
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define container_of(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))
#define QCOM_USB4_IDLE_STOP_MS 500
#define QCOM_USB4_SURFACE_BOARD_RETIMER 1
#define USB_TYPEC_DP_SID 0xff01
#define USB_TYPEC_TBT_SID 0x8087
enum {TYPEC_STATE_SAFE,TYPEC_STATE_USB,TYPEC_STATE_MODAL};
#define TYPEC_MODE_USB4 4
enum typec_orientation {TYPEC_ORIENTATION_NONE,TYPEC_ORIENTATION_NORMAL,TYPEC_ORIENTATION_REVERSE};
enum qcom_usb4_link_request {QCOM_USB4_LINK_NONE,QCOM_USB4_LINK_CONNECT,QCOM_USB4_LINK_DISCONNECT};
struct mutex {int held;};
struct work_struct {int unused;};
struct delayed_work {struct work_struct work;long delay;int queued;};
struct device {int unused;};
struct typec_altmode {unsigned short svid;};
struct enter_usb_data {u32 eudo;};
struct typec_mux_state {struct typec_altmode *alt;unsigned long mode;void *data;};
struct typec_mux_dev {void *drvdata;};
struct qcom_usb4_dp {int connected_calls;bool connected;bool active;};
struct qcom_usb4_host {
 struct device *dev;unsigned int port;struct qcom_usb4_dp *dp;
 struct mutex lock;enum typec_orientation orientation;enum qcom_usb4_link_request pending;u32 pending_command;bool connected;
 bool started;bool released;bool removing;struct mutex lifecycle_lock;struct delayed_work lifecycle_work;
};
static void *system_long_wq;
static int commands,releases,acquires,acquire_error;
static u32 last_command;
static void mutex_lock(struct mutex*m){assert(!m->held);m->held=1;}
static void mutex_unlock(struct mutex*m){assert(m->held);m->held=0;}
#define lockdep_assert_held(m) assert((m)->held)
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define dev_warn(d,f,...) ((void)(d),(void)sizeof(printf(f,__VA_ARGS__)))
#define dev_err(...) ((void)0)
static long msecs_to_jiffies(long ms){return ms;}
static struct delayed_work *to_delayed_work(struct work_struct*w){return container_of(w,struct delayed_work,work);}
static bool mod_delayed_work(void*wq,struct delayed_work*w,long delay){(void)wq;w->queued=1;w->delay=delay;return true;}
static void *typec_mux_get_drvdata(struct typec_mux_dev*m){return m->drvdata;}
static int qcom_usb4_typec_usb4_command(const struct enter_usb_data*d,enum typec_orientation o,unsigned b,u32*c){(void)d;(void)o;(void)b;*c=0x2501;return 0;}
static int qcom_usb4_typec_tbt_command(const void*d,enum typec_orientation o,unsigned b,u32*c){(void)d;(void)o;(void)b;*c=0x2401;return 0;}
static int qcom_usb4_typec_disconnect_command(u32*c){*c=6;return 0;}
static int fail_command;
static int qcom_usb4_host_send_command(struct qcom_usb4_host*h,u32 c,const char*w){(void)w;assert(h->started&&h->lock.held);commands++;last_command=c;return fail_command?-ETIMEDOUT:0;}
static void qcom_usb4_dp_set_connected(struct qcom_usb4_dp*dp,bool c){dp->connected_calls++;dp->connected=c;}
static bool qcom_usb4_dp_active(struct qcom_usb4_dp*dp){return dp->active;}
static void qcom_usb4_host_apply_link(struct qcom_usb4_host *host);
/* Hardware effects of the real release/acquire paths, which are not extracted. */
static void qcom_usb4_host_release(struct qcom_usb4_host*h){assert(!h->lock.held&&h->lifecycle_lock.held&&!h->started&&!h->connected);releases++;h->released=true;}
static int qcom_usb4_host_acquire(struct qcom_usb4_host*h){
 assert(!h->lock.held&&h->lifecycle_lock.held&&h->released&&!h->started);acquires++;
 if(acquire_error)return acquire_error;
 mutex_lock(&h->lock);h->released=false;h->started=true;qcom_usb4_host_apply_link(h);mutex_unlock(&h->lock);return 0;
}
'''
post=r'''
static struct qcom_usb4_dp dp;static struct qcom_usb4_host host;static struct typec_mux_dev mux={&host};
static struct typec_altmode dpalt={USB_TYPEC_DP_SID},tbt={USB_TYPEC_TBT_SID};
static struct enter_usb_data eudo={0x1};static int cases;
static void reset(bool started){memset(&host,0,sizeof(host));memset(&dp,0,sizeof(dp));host.dp=&dp;host.started=started;host.orientation=TYPEC_ORIENTATION_NORMAL;commands=releases=acquires=acquire_error=0;}
static void set(struct typec_altmode*alt,unsigned long mode,void*data){struct typec_mux_state s={alt,mode,data};assert(!qcom_usb4_host_mux_set(&mux,&s));assert(!host.lock.held);}
static void dpmode(unsigned long pin){set(&dpalt,TYPEC_STATE_MODAL+pin,NULL);}
static void safe(void){set(NULL,TYPEC_STATE_SAFE,NULL);}
static void usb(void){set(NULL,TYPEC_STATE_USB,NULL);}
static void usb4(void){set(NULL,TYPEC_MODE_USB4,&eudo);}
/* Only a delayed work item that is still queued runs; mod_delayed_work re-arms it. */
static void run(void){if(!host.lifecycle_work.queued)return;host.lifecycle_work.queued=0;qcom_usb4_host_lifecycle_work(&host.lifecycle_work.work);assert(!host.lock.held&&!host.lifecycle_lock.held);}
int main(void){
 /* Idle port: HDMI cable (USB, DP pin C, HPD/IRQ_HPD) and a USB drive never touch the router. */
 reset(false);host.released=true;usb();dpmode(2);dpmode(2);safe();usb();usb();
 assert(!host.lifecycle_work.queued&&!acquires&&!releases&&!commands);cases++;
 /* Dell attach from idle: four USB reports then USB4 entry starts the router at once. */
 usb();usb();usb();usb();usb4();assert(host.lifecycle_work.queued&&host.lifecycle_work.delay==0);
 run();assert(acquires==1&&host.started&&host.connected&&commands==1&&last_command==0x2501&&dp.connected);cases++;
 /* UCSI USB state and IRQ_HPD-style repeats while connected change nothing. */
 usb();run();assert(!releases&&host.connected);cases++;
 /* Dell unplug: disconnect is sent, the stop waits for the DP tunnel to be released. */
 dp.active=true;safe();assert(last_command==6&&!host.connected&&host.lifecycle_work.queued&&host.lifecycle_work.delay==500);
 run();assert(!releases&&host.lifecycle_work.queued&&host.lifecycle_work.delay==500);
 run();assert(!releases);dp.active=false;run();assert(releases==1&&host.released&&!host.started);cases++;
 /* The next plain partner finds the port idle. */
 usb();dpmode(2);assert(!host.lifecycle_work.queued);cases++;
 /* A failed disconnect command keeps the connection and the router. */
 reset(true);host.connected=true;fail_command=1;safe();fail_command=0;run();assert(host.connected&&host.started&&!releases);cases++;
 /* Quick replug inside the idle window reconnects without stopping. */
 reset(true);host.connected=true;safe();assert(host.lifecycle_work.queued);usb();usb4();
 assert(host.connected&&commands==2);run();assert(!releases&&host.started);cases++;
 /* Boot replay with the Dell attached before probe: requests are deferred until ready. */
 reset(false);dpmode(3);safe();usb();usb4();assert(!host.lifecycle_work.queued&&host.pending==QCOM_USB4_LINK_CONNECT);
 host.released=true;host.lifecycle_work.queued=1;host.lifecycle_work.delay=0;run();
 assert(acquires==1&&host.connected&&last_command==0x2501);cases++;
 /* A USB4 entry that leaves before the work runs does not start the router. */
 reset(false);host.released=true;usb4();safe();run();assert(!acquires&&host.released);cases++;
 /* TBT3 entry also starts it. */
 reset(false);host.released=true;set(&tbt,TYPEC_STATE_MODAL,&(int){0});run();assert(acquires==1&&host.connected&&last_command==0x2401);cases++;
 /* A failed start stays ready and a later entry tries again. */
 reset(false);host.released=true;acquire_error=-EIO;usb4();run();assert(acquires==1&&host.released&&!host.started);
 acquire_error=0;safe();usb4();run();assert(acquires==2&&host.started&&host.connected);cases++;
 /* Router not ready (firmware missing or startup disabled): nothing is queued. */
 reset(false);usb4();safe();dpmode(2);assert(!host.lifecycle_work.queued&&!acquires);cases++;
 /* Removal: no new decisions and a pending run does nothing. */
 reset(true);host.connected=true;host.removing=true;safe();assert(!host.lifecycle_work.queued);
 host.lifecycle_work.queued=1;run();assert(!releases);host.removing=false;cases++;
 printf("PASS %d extracted router port-ownership sequences\n",cases);
}
'''
FLAGS=['-Wall', '-Werror', '-Wno-unused-function']
MUTATIONS=[
 ('connect_needs_started_router','request == QCOM_USB4_LINK_CONNECT && host->released','request == QCOM_USB4_LINK_CONNECT && host->started'),
 ('idle_stop_ignores_disconnect_state','request == QCOM_USB4_LINK_DISCONNECT && host->started','request == QCOM_USB4_LINK_DISCONNECT'),
 ('immediate_idle_stop','&host->lifecycle_work,\n\t\t\t\t\t msecs_to_jiffies(QCOM_USB4_IDLE_STOP_MS));\n\t}','&host->lifecycle_work, 0);\n\t}'),
 ('stop_during_dp_tunnel','if (release && qcom_usb4_dp_active(host->dp))','if (0)'),
 ('stop_while_connected','host->started && !host->connected;','host->started;'),
 ('stop_during_removal','release = !host->removing && ','release = '),
 ('queue_during_removal','if (!host->removing) {','if (true) {'),
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
