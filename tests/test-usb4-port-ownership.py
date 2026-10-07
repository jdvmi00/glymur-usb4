#!/usr/bin/env python3
"""Exercise the actual router port-ownership and system-sleep decisions against
recorded Type-C sequences: start only for USB4/TBT partners, stop after they
leave, stop-and-restart around hibernation, and keep a connected router across
s2idle, including a partner that leaves while the router is asleep."""
from pathlib import Path
import argparse, re, subprocess, tempfile, json
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True,help='drivers/thunderbolt/qcom-usb4-host.c');ap.add_argument('--output',type=Path);args=ap.parse_args();source=args.source.read_text()
def extract(name):
 m=re.search(r'(?m)^static [^;{}]*?\b'+name+r'\([^;{}]*\)\s*\{',source);assert m,name
 start=m.start();end=m.end();depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
NAMES=('qcom_usb4_host_apply_link','qcom_usb4_host_mux_set','qcom_usb4_host_lifecycle_work',
 'qcom_usb4_host_sleep_prepare','qcom_usb4_host_sleep_complete','qcom_usb4_host_link_resumed','qcom_usb4_host_resume_link')
functions='\n'.join(extract(n) for n in NAMES)
# Constants are taken from the source rather than restated.
DEFINES=('QCOM_USB4_IDLE_STOP_MS','QCOM_USB4_SLEEP_STOP_MS','QCOM_USB4_SURFACE_BOARD_RETIMER','QCOM_USB4_MCU_RESUME_COMMAND',
 'QCOM_USB4_WAKE_STATUS','QCOM_USB4_LANE0_STATUS','QCOM_USB4_LANE_STATE','QCOM_USB4_LANE_STATE_ACTIVE',
 'QCOM_USB4_LINK_RESUME_TIMEOUT_MS','QCOM_USB4_COMMAND_TIMEOUT_US')
defines='\n'.join(re.search(r'(?m)^#define '+n+r'\s.*$',source)[0] for n in DEFINES)
assert re.search(r'(?m)^#define QCOM_USB4_IDLE_STOP_MS\s+500$',source) and re.search(r'(?m)^#define QCOM_USB4_SLEEP_STOP_MS\s+5000$',source)
# The router is powered only while it runs, and releases its block reset before power-off (1.90, 1.91).
acquire=extract('qcom_usb4_host_acquire');stop_all=extract('qcom_usb4_host_stop_all');power_off=extract('qcom_usb4_host_power_off')
assert acquire.index('qcom_usb4_host_power_on(host)')<acquire.index('qcom_usb4_host_start(host)')
assert acquire.count('qcom_usb4_host_power_off(host);')==1 and stop_all.rstrip().endswith('qcom_usb4_host_power_off(host);\n}')
assert 'pm_runtime_allow(host->dev);' in stop_all
assert power_off.index('reset_control_deassert(host->router_reset)')<power_off.index('pm_runtime_put_sync(host->dev)')
assert 'qcom_usb4_host_stop_all(host);' in extract('qcom_usb4_host_release') and 'qcom_usb4_host_stop_all(host);' in extract('qcom_usb4_host_teardown')
# Probe neither starts nor powers the router; it starts runtime-active so the idle drops the CX vote (1.96).
probe=extract('qcom_usb4_host_probe')
assert 'qcom_usb4_host_start(' not in probe and 'pm_runtime_resume_and_get' not in probe and 'clocks_enable' not in probe
assert probe.index('pm_runtime_set_active(dev)')<probe.index('devm_pm_runtime_enable(dev)')<probe.index('register_pm_notifier(&host->pm_nb)')
assert 'host->released = true;\n\tif (host->pending == QCOM_USB4_LINK_CONNECT)\n\t\tmod_delayed_work(system_long_wq, &host->lifecycle_work, 0);' in probe
assert '.suppress_bind_attrs = true' in source and '.pm = &qcom_usb4_host_pm_ops,' in source
# Only suspend keeps a router; hibernation stops it (1.142).
assert 'qcom_usb4_host_sleep_prepare(host, action == PM_SUSPEND_PREPARE)' in extract('qcom_usb4_host_pm_notify')
# While running, the router holds the tunnelled xHCI and the PHY runtime reference (1.146, 1.149).
assert acquire.index('qcom_usb4_host_hold_xhci(host);')<acquire.index('qcom_usb4_host_apply_link(host);')
stop_hw=extract('qcom_usb4_host_stop_hardware')
assert stop_hw.index('phy_power_off(host->phy)')<stop_hw.index('phy_exit(host->phy)') and 'qcom_usb4_host_release_xhci(host);' in stop_hw
provider=extract('qcom_usb4_host_provider');assert provider.index('phy_init(')<provider.index('phy_power_on(host->phy)')
suspend=extract('qcom_usb4_host_suspend')
assert suspend.index('nhi_pm_ops.suspend_noirq(dev)')<suspend.index('qcom_usb4_host_halt(host)')<suspend.index('device_set_awake_path(dev)')
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)<<(l))&(~0U>>(31-(h))))
#define FIELD_GET(m,v) (((v)&(m))>>__builtin_ctz(m))
#define container_of(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))
'''+defines+r'''
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
struct qcom_usb4_dp {int connected_calls;bool connected;bool active;int prepares,prepare_error,completes,discovers;bool complete_connected;};
struct tb_nhi {bool going_away;};
struct qcom_usb4_nhi {struct tb_nhi nhi;};
struct qcom_usb4_mcu {int unused;};
struct qcom_usb4_host {
 struct device *dev;unsigned int port;struct qcom_usb4_dp *dp;struct qcom_usb4_mcu mcu;struct qcom_usb4_nhi qnhi;
 struct mutex lock;enum typec_orientation orientation;enum qcom_usb4_link_request pending;u32 pending_command;bool connected;u32 connect_command;
 bool started;bool released;bool removing;bool suspending;bool resume_connect;bool kept;bool mcu_halted;bool sleep_failed;
 struct mutex lifecycle_lock;struct delayed_work lifecycle_work;bool nhi_probed;
};
static struct qcom_usb4_dp dp;
static void *system_long_wq;
static int commands,releases,released_connected,acquires,acquire_error,warnings,errors,infos;
static u32 last_command;
static void mutex_lock(struct mutex*m){assert(!m->held);m->held=1;}
static void mutex_unlock(struct mutex*m){assert(m->held);m->held=0;}
#define lockdep_assert_held(m) assert((m)->held)
#define dev_info(...) (infos++)
#define dev_dbg(...) ((void)0)
#define dev_warn(d,f,...) ((void)(d),(void)sizeof(printf(f,__VA_ARGS__)),warnings++)
#define dev_err(d,f,...) ((void)(d),(void)sizeof(printf(f,__VA_ARGS__)),errors++)
/* Simulated time: jiffies are milliseconds; DRM releases the tunnel after dp_release_ms. */
static unsigned long jiffies;static long dp_release_ms=-1;
static long msecs_to_jiffies(long ms){return ms;}
#define time_after(a,b) ((long)((b)-(a))<0)
static void msleep(unsigned ms){jiffies+=ms;if(dp_release_ms>=0&&(long)jiffies>=dp_release_ms)dp.active=false;}
static void qcom_usb4_host_lifecycle_work(struct work_struct *work);
static struct delayed_work *to_delayed_work(struct work_struct*w){return container_of(w,struct delayed_work,work);}
static bool mod_delayed_work(void*wq,struct delayed_work*w,long delay){(void)wq;w->queued=1;w->delay=delay;return true;}
static void flush_delayed_work(struct delayed_work*w){if(w->queued){w->queued=0;qcom_usb4_host_lifecycle_work(&w->work);}}
static void *typec_mux_get_drvdata(struct typec_mux_dev*m){return m->drvdata;}
static int qcom_usb4_typec_usb4_command(const struct enter_usb_data*d,enum typec_orientation o,unsigned b,u32*c){(void)d;(void)o;(void)b;*c=0x2501;return 0;}
static int qcom_usb4_typec_tbt_command(const void*d,enum typec_orientation o,unsigned b,u32*c){(void)d;(void)o;(void)b;*c=0x2401;return 0;}
static int qcom_usb4_typec_disconnect_command(u32*c){*c=6;return 0;}
static int fail_command;
/* Connection commands through the running firmware; a halted MCU must never get one. */
static int qcom_usb4_host_send_command(struct qcom_usb4_host*h,u32 c,const char*w){(void)w;assert(h->started&&h->lock.held&&!h->mcu_halted);commands++;last_command=c;return fail_command?-ETIMEDOUT:0;}
/* Router registers and MCU commands seen by the resume path. */
static u32 wake_status;static long lane_ready_ms;static u32 mcu_cmds[8];static int mcu_count,mcu_fail_connect;
static int qcom_usb4_host_read_router(void*ctx,u32 off,u32*v){struct qcom_usb4_host*h=ctx;assert(h->lock.held);
 if(off==QCOM_USB4_WAKE_STATUS){*v=wake_status;return 0;}
 assert(off==QCOM_USB4_LANE0_STATUS);*v=(lane_ready_ms>=0&&(long)jiffies>=lane_ready_ms)?(2U<<26):(7U<<26);return 0;}
static int qcom_usb4_mcu_command(struct qcom_usb4_mcu*m,u32 c,unsigned t){(void)m;assert(t==QCOM_USB4_COMMAND_TIMEOUT_US&&mcu_count<8);mcu_cmds[mcu_count++]=c;
 return (mcu_fail_connect&&c==0x2501)?-ETIMEDOUT:0;}
static void qcom_usb4_dp_set_connected(struct qcom_usb4_dp*d,bool c){d->connected_calls++;d->connected=c;}
static bool qcom_usb4_dp_active(struct qcom_usb4_dp*d){return d->active;}
static int qcom_usb4_dp_sleep_prepare(struct qcom_usb4_dp*d){d->prepares++;return d->prepare_error;}
static int qcom_usb4_dp_sleep_complete(struct qcom_usb4_dp*d,bool c){d->completes++;d->complete_connected=c;return 0;}
static int qcom_usb4_dp_resume_discover(struct qcom_usb4_dp*d){d->discovers++;return 0;}
static void qcom_usb4_host_apply_link(struct qcom_usb4_host *host);
/* Effects of the real release/acquire paths, which are not extracted: the
 * stop clears the run state; the start runs and applies the pending link. */
static void qcom_usb4_host_release(struct qcom_usb4_host*h){
 assert(!h->lock.held&&h->lifecycle_lock.held&&!h->started);releases++;if(h->connected)released_connected++;
 h->connected=false;h->mcu_halted=false;h->released=true;}
static int qcom_usb4_host_acquire(struct qcom_usb4_host*h){
 assert(!h->lock.held&&h->lifecycle_lock.held&&h->released&&!h->started);acquires++;
 if(acquire_error)return acquire_error;
 mutex_lock(&h->lock);h->released=false;h->started=true;qcom_usb4_host_apply_link(h);mutex_unlock(&h->lock);return 0;
}
'''
post=r'''
static struct qcom_usb4_host host;static struct typec_mux_dev mux={&host};
static struct typec_altmode dpalt={USB_TYPEC_DP_SID},tbt={USB_TYPEC_TBT_SID};
static struct enter_usb_data eudo={0x1};static int cases;static int halt_error;
static void reset(bool started){memset(&host,0,sizeof(host));memset(&dp,0,sizeof(dp));host.dp=&dp;host.started=started;host.orientation=TYPEC_ORIENTATION_NORMAL;
 commands=releases=released_connected=acquires=acquire_error=warnings=errors=infos=0;jiffies=0;dp_release_ms=-1;
 fail_command=halt_error=0;wake_status=0;lane_ready_ms=0;mcu_count=mcu_fail_connect=0;}
static void set(struct typec_altmode*alt,unsigned long mode,void*data){struct typec_mux_state s={alt,mode,data};assert(!qcom_usb4_host_mux_set(&mux,&s));assert(!host.lock.held);}
static void dpmode(unsigned long pin){set(&dpalt,TYPEC_STATE_MODAL+pin,NULL);}
static void safe(void){set(NULL,TYPEC_STATE_SAFE,NULL);}
static void usb(void){set(NULL,TYPEC_STATE_USB,NULL);}
static void usb4(void){set(NULL,TYPEC_MODE_USB4,&eudo);}
/* Only a delayed work item that is still queued runs; mod_delayed_work re-arms it. */
static void run(void){if(!host.lifecycle_work.queued)return;host.lifecycle_work.queued=0;qcom_usb4_host_lifecycle_work(&host.lifecycle_work.work);assert(!host.lock.held&&!host.lifecycle_lock.held);}
/* A running Dell or dock connection (after a USB4 entry from idle), with its NHI probed. */
static void dell(void){reset(false);host.released=true;usb4();run();assert(host.connected&&host.started);host.nhi_probed=true;commands=acquires=0;}
static int prepare(bool keep){int r=qcom_usb4_host_sleep_prepare(&host,keep);assert(!host.lock.held&&!host.lifecycle_lock.held);return r;}
static void complete(void){qcom_usb4_host_sleep_complete(&host);assert(!host.lock.held&&!host.lifecycle_lock.held);}
/* Models of the router's .suspend/.resume (not extracted): the connection
 * manager's router sleep, the MCU halt, then at resume the warm start and the
 * extracted link resume, under the host lock as qcom_usb4_host_warm_start(). */
static void pm_suspend(void){if(!host.kept)return;
 if(!host.started||!host.nhi_probed){host.sleep_failed=true;}
 if(host.sleep_failed)return;
 if(halt_error){host.sleep_failed=true;return;}
 mutex_lock(&host.lock);host.mcu_halted=true;mutex_unlock(&host.lock);}
static void pm_resume(void){if(!host.kept||host.sleep_failed)return;mutex_lock(&host.lock);host.mcu_halted=false;
 if(qcom_usb4_host_resume_link(&host)){host.sleep_failed=true;}
 mutex_unlock(&host.lock);}
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
 /* Router not ready (no firmware): nothing is queued. */
 reset(false);usb4();safe();dpmode(2);assert(!host.lifecycle_work.queued&&!acquires);cases++;
 /* Removal: no new decisions and a pending run does nothing. */
 reset(true);host.connected=true;host.removing=true;safe();assert(!host.lifecycle_work.queued);
 host.lifecycle_work.queued=1;run();assert(!releases);host.removing=false;cases++;

 /* Hibernation with the Dell and its DP tunnel: save the display, detach like an unplug, stop once DRM lets go. */
 dell();dp.active=true;dp_release_ms=700;assert(!prepare(false));
 assert(dp.prepares==1&&last_command==6&&!host.connected&&!dp.connected&&releases==1&&!released_connected&&!host.started&&host.released&&!host.kept);
 assert(host.suspending&&host.resume_connect&&!errors&&jiffies>=700&&jiffies<1500);
 /* Nothing restarts it before resume; afterwards the partner is reconnected like a new plug, then the display restored. */
 run();assert(!acquires);complete();assert(!host.suspending&&acquires==1&&host.connected&&last_command==0x2501&&dp.connected);
 assert(dp.completes==1&&dp.complete_connected);cases++;
 /* Idle port: sleep neither stops nor starts anything; the display side is told there is no tunnel. */
 reset(false);host.released=true;assert(!prepare(true));assert(!releases&&!commands&&!host.resume_connect&&!dp.prepares&&!host.kept);
 complete();run();assert(!acquires&&dp.completes==1&&!dp.complete_connected);cases++;
 /* Unplugged while hibernating: the safe state on resume wins over the reconnect. */
 dell();assert(!prepare(false));assert(releases==1);safe();complete();run();assert(!acquires&&host.released);cases++;
 /* Plugged in while suspending: no start until resume, then a synchronous start. */
 reset(false);host.released=true;assert(!prepare(true));usb4();run();assert(!acquires);
 complete();assert(acquires==1&&host.connected&&dp.complete_connected);cases++;
 /* DRM never releases the tunnel: refuse sleep after the bound; undoing the preparation reconnects. */
 dell();dp.active=true;assert(prepare(false)==-EBUSY);assert(errors==1&&host.started&&!releases&&jiffies>=5000&&jiffies<6000);
 complete();assert(host.connected&&last_command==0x2501&&!acquires&&dp.complete_connected);cases++;
 /* A reconnect that fails after hibernation (partner gone, no event) leaves the display disconnected. */
 dell();assert(!prepare(false));fail_command=1;complete();fail_command=0;assert(acquires==1&&!host.connected&&!dp.complete_connected);cases++;
 /* Suspend during the idle-stop window (running, no partner) does not keep the router. */
 reset(true);host.nhi_probed=true;assert(!prepare(true));assert(!host.kept&&releases==1&&!host.started);complete();assert(!acquires);cases++;
 /* Suspend before the NHI is probed does not keep it either. */
 dell();host.nhi_probed=false;assert(!prepare(true));assert(!host.kept&&releases==1&&last_command==6);complete();assert(acquires==1&&host.connected);cases++;

 /* Docked suspend: the router is kept; no disconnect, no stop, and the lifecycle leaves it alone. */
 dell();assert(!prepare(true));assert(host.kept&&host.started&&host.connected&&!commands&&!releases&&dp.prepares==1);
 flush_delayed_work(&host.lifecycle_work);run();assert(!releases);
 pm_suspend();assert(host.mcu_halted);wake_status=0;pm_resume();
 /* Wake type 3 (no wake bits): resume command 0x305, then the lane is active. */
 assert(!host.mcu_halted&&mcu_count==1&&mcu_cmds[0]==0x305&&host.connected&&!host.sleep_failed);
 complete();assert(!host.kept&&!host.suspending&&dp.discovers==1&&dp.completes==1&&dp.complete_connected&&host.lifecycle_work.queued);
 run();assert(!releases&&host.started&&host.connected);cases++;
 /* Wake type 2 (bit 16): the connection's connect command is repeated. */
 dell();assert(!prepare(true));pm_suspend();wake_status=BIT(16);pm_resume();
 assert(mcu_count==2&&mcu_cmds[0]==0x205&&mcu_cmds[1]==0x2501&&host.connected);complete();run();assert(!releases);cases++;
 /* Wake type 2 whose connect fails: the partner is treated as gone. */
 dell();assert(!prepare(true));pm_suspend();wake_status=BIT(16);mcu_fail_connect=1;pm_resume();
 assert(!host.connected&&mcu_cmds[mcu_count-1]==6&&infos==1);complete();assert(!dp.complete_connected);run();assert(releases==1&&!released_connected);cases++;
 /* Wake type 1 (bit 17, a disconnect wake): gone even if the lane still reads active. */
 dell();assert(!prepare(true));pm_suspend();wake_status=BIT(17);pm_resume();
 assert(mcu_cmds[0]==0x105&&mcu_cmds[1]==6&&!host.connected&&jiffies<100);complete();assert(!dp.complete_connected);run();assert(releases==1);cases++;
 /* Wake type 0 (bit 18) and a lane that never returns: gone after the 5 s bound. */
 dell();assert(!prepare(true));pm_suspend();wake_status=BIT(18);lane_ready_ms=-1;pm_resume();
 assert(mcu_cmds[0]==0x005&&!host.connected&&jiffies>=5000&&jiffies<5100);complete();run();assert(releases==1);cases++;
 /* Undocked while asleep: the request waits for the MCU, then wins over a lane that still reads active. */
 dell();assert(!prepare(true));pm_suspend();safe();assert(!commands&&host.pending==QCOM_USB4_LINK_DISCONNECT&&host.connected);
 run();assert(!releases);pm_resume();
 assert(mcu_count==2&&mcu_cmds[1]==6&&!host.connected&&host.pending==QCOM_USB4_LINK_NONE&&jiffies<100);
 complete();assert(!dp.connected&&!dp.complete_connected);run();assert(releases==1&&!released_connected&&host.released);cases++;
 /* A disconnect between the notifier and .suspend: the lifecycle must not stop the kept router. */
 dell();assert(!prepare(true));safe();assert(last_command==6&&!host.connected);run();assert(!releases&&host.started);
 pm_suspend();lane_ready_ms=-1;pm_resume();complete();run();assert(releases==1);cases++;
 /* A kept router whose sleep failed (halt error) is restarted after resume and reconnected. */
 dell();assert(!prepare(true));halt_error=1;pm_suspend();pm_resume();assert(host.sleep_failed&&!mcu_count);
 complete();assert(releases==1&&host.qnhi.nhi.going_away&&warnings==1&&acquires==1&&host.connected&&!host.kept&&!host.sleep_failed);
 assert(dp.complete_connected&&!dp.discovers);cases++;
 printf("PASS %d extracted router port-ownership and sleep sequences\n",cases);
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
 ('kept_router_released','!host->kept && host->started','host->started'),
 ('command_to_halted_mcu','if (!host->started || host->mcu_halted)','if (!host->started)'),
 ('keep_unconnected_router','if (keep && started && host->connected && !host->removing && host->nhi_probed)','if (keep && started && !host->removing && host->nhi_probed)'),
 ('keep_without_nhi','if (keep && started && host->connected && !host->removing && host->nhi_probed)','if (keep && started && host->connected && !host->removing)'),
 ('ignore_pending_disconnect','if (host->pending != QCOM_USB4_LINK_DISCONNECT &&\n\t    qcom_usb4_host_link_resumed(host, type))','if (qcom_usb4_host_link_resumed(host, type))'),
 ('disconnect_wake_ignored','\tif (type == 1)\n\t\treturn false;\n',''),
 ('failed_sleep_not_restarted','if (host->kept && !host->sleep_failed) {','if (host->kept) {'),
 ('no_dp_rediscovery','ret = qcom_usb4_dp_resume_discover(host->dp);','ret = 0;'),
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
