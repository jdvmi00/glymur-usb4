#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile,json,argparse,re
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
parser=argparse.ArgumentParser(description='Exercise the actual USB4 idle helper with scripted MMIO and completion events')
parser.add_argument('--source',required=True,type=Path,help='candidate drivers/gpu/drm/msm/dp/dp_ctrl.c')
parser.add_argument('--output',type=Path,help='optional JSON result file')
args=parser.parse_args();s=args.source.read_text();a=s.index('void msm_dp_ctrl_push_idle(');b=s.index('\nstatic void ',a);fn=s[a:b]
pre=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define DP_MAINLINK_READY_FOR_IDLE BIT(1)
#define REG_DP_MAINLINK_READY 0x40
#define REG_DP_STATE_CTRL 4
#define DP_STATE_CTRL_PUSH_IDLE 0x100
#define IDLE_PATTERN_COMPLETION_TIMEOUT_JIFFIES 30
struct msm_dp_ctrl {int unused;};
struct msm_dp_ctrl_private {struct msm_dp_ctrl msm_dp_ctrl; void *aux; unsigned char *link_base; void *dev,*drm_dev; int idle_comp;};
#define container_of(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))
static bool tunneled,complete;
static int writes, polls, delays, waits, resets, warnings, infos;
static unsigned values[4], next_value, reads_until_ready;
static unsigned char regs[256];
static bool msm_dp_aux_usb4_attached(void *a) {(void)a;return tunneled;}
static void msm_dp_write_link(struct msm_dp_ctrl_private *c,int r,unsigned v) {(void)c;assert(r==4);assert(writes<4);values[writes++]=v;}
static void reinit_completion(int *c) {(void)c;resets++;}
static int wait_for_completion_timeout(int*c,int t) {(void)c;assert(!tunneled&&t==30);waits++;return complete;}
#define dev_warn(...) (warnings++)
#define dev_info(...) (infos++)
#define pr_warn(...) (warnings++)
#define drm_dbg_dp(...) ((void)0)
#define readl_poll_timeout(addr,value,condition,sleep_us,timeout_us) ({ \
 assert((addr)==regs+0x40); assert((sleep_us)==100 && (timeout_us)==30000); \
 assert(tunneled && writes==2 && values[0]==0 && values[1]==0x100); \
 int result=-110; polls++; for(int q=0;q<301;q++){ \
 value=q<(int)reads_until_ready?0x80001:next_value;delays++; \
 if(condition){result=0;break;} } result; })
'''
actual_macro=re.search(r'^#define DP_MAINLINK_READY_FOR_IDLE .+$',s,re.M)
assert actual_macro, 'missing idle status definition'
pre=pre.replace('#define DP_MAINLINK_READY_FOR_IDLE BIT(1)',actual_macro[0])
post=r'''
int main(void) {
 struct msm_dp_ctrl_private ctrl={.link_base=regs}; int cases=0;
 for(int mode=0;mode<2;mode++) for(unsigned v=0;v<256;v++) for(unsigned delay=0;delay<2;delay++) {
  tunneled=mode; complete=!!(v&1); next_value=v; reads_until_ready=delay?7:0;
  writes=polls=delays=waits=resets=warnings=infos=0;
  msm_dp_ctrl_push_idle(&ctrl.msm_dp_ctrl);
  if(mode) { assert(writes==2&&values[0]==0&&values[1]==0x100&&polls==1&&!waits&&!resets);
   assert(warnings==!(v&2));assert(infos==!!(v&2));assert(delays==((v&2)?(delay?8:1):301)); }
  else {assert(writes==1&&values[0]==0x100&&!polls&&waits==1&&resets==1);assert(warnings==!complete);}
  cases++;
 }
 printf("PASS %d extracted-function cases\n",cases);
}
'''
with tempfile.TemporaryDirectory() as t:
 d=Path(t);f=d/'test.c';f.write_text(pre+fn+post)
 subprocess.run(['cc','-include',HARNESS_HEADER,'-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-o',str(d/'test'),str(f)],check=True)
 r=subprocess.run([str(d/'test')],check=True,capture_output=True,text=True);print(r.stdout,end='')
 mutants={'wrong_ready_bit':fn.replace('ready & DP_MAINLINK_READY_FOR_IDLE','ready & BIT(0)'), 'missing_state_clear':fn.replace('\t\tmsm_dp_write_link(ctrl, REG_DP_STATE_CTRL, 0);\n',''), 'suppressed_timeout':fn.replace('if (ret)\n','if (0)\n')}
 result={}
 for name,mutant in mutants.items():
  assert mutant!=fn
  f.write_text(pre+mutant+post)
  c=subprocess.run(['cc','-include',HARNESS_HEADER,'-std=gnu11','-w','-o',str(d/'bad'),str(f)],capture_output=True,text=True);assert c.returncode==0,c.stderr
  r=subprocess.run([str(d/'bad')],capture_output=True,text=True);assert r.returncode==134,name
  result[name]='rejected'
 if args.output:args.output.write_text(json.dumps({'actual_function_cases':1024,'ASan_UBSan':'pass','negative_controls':result},indent=2)+'\n')
 print('Negative controls:',result)
