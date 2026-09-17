#!/usr/bin/env python3
"""Exercise extracted FEC readiness and start functions against a stateful sink."""
from pathlib import Path
import argparse, json, subprocess, tempfile
HARNESS_HEADER=str(Path(__file__).resolve().with_name('harness.h'))
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--provider',type=Path,required=True)
ap.add_argument('--ctrl',type=Path,required=True)
ap.add_argument('--output',type=Path)
a=ap.parse_args();provider=a.provider.read_text();ctrl=a.ctrl.read_text()
def extract(src,name):
 start=src.rfind('static ',0,src.index(name+'('));i=src.index('{',start)+1;level=1
 while level:
  level+=(src[i]=='{')-(src[i]=='}');i+=1
 return src[start:i]
assert 'fec_setup_attempted' not in provider
assert 'fec_dsc_probe' not in provider
assert 'usb4_fec_pattern_probe' not in ctrl
train=extract(ctrl,'msm_dp_ctrl_link_train')
assert train.index('msm_dp_ctrl_fec_config(ctrl, false)')<train.index('msm_dp_aux_usb4_set_fec_ready')
func=extract(provider,'dp_set_fec_ready')+'\n'+extract(ctrl,'msm_dp_ctrl_fec_start')
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <errno.h>
typedef uint8_t u8;
#define DP_FEC_CONFIGURATION 0x120
#define DP_FEC_STATUS 0x280
#define DP_FEC_READY 1
#define DP_FEC_DECODE_EN_DETECTED 1
#define DP_FEC_DECODE_DIS_DETECTED 2
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define drm_dbg_dp(...) ((void)0)
#define DRM_ERROR(...) ((void)0)
struct qcom_usb4_dp {int aux;};
struct msm_dp_ctrl_private {void *aux;};
static bool source_on,emit_fec,stuck_ready,stuck_flags;
static u8 ready,status;
static int operations,fail_at,control_calls,clear_calls,zero_calls,attempts;
static int op(void){return ++operations==fail_at?-EREMOTEIO:0;}
static int drm_dp_dpcd_read_byte(void*p,int reg,u8*v){(void)p;int r=op();if(r)return r;*v=reg==DP_FEC_CONFIGURATION?ready:status;return 0;}
static int drm_dp_dpcd_write_byte(void*p,int reg,u8 v){(void)p;assert(!source_on);int r=op();if(r)return r;
 if(reg==DP_FEC_CONFIGURATION){if(!v)zero_calls++;if(!stuck_ready)ready=v;}
 else{assert(reg==DP_FEC_STATUS);clear_calls++;if(!stuck_flags)status&=~(v&3);}
 return 0;
}
static int dp_control(struct qcom_usb4_dp*p,u8 tx[4],u8 rx[4]){(void)p;rx[0]=0x80;rx[1]=0x0a;rx[2]=0;rx[3]=0x89;assert(!source_on);int r=op();if(r)return r;
 assert(tx[1]==0xa&&tx[2]==0&&tx[3]==0&&tx[0]==(ready&1));assert(!(status&3));control_calls++;return 0;
}
static bool msm_dp_aux_usb4_attached(void*p){(void)p;return true;}
static void msm_dp_ctrl_fec_config(struct msm_dp_ctrl_private*p,bool on){(void)p;source_on=on;if(on){attempts++;if(emit_fec)status|=1;}}
static void usleep_range(int a,int b){(void)a;(void)b;}
static void reset(u8 r,u8 s){ready=r;status=s;source_on=false;emit_fec=false;stuck_ready=stuck_flags=false;operations=control_calls=clear_calls=zero_calls=attempts=0;fail_at=0;}
'''
main=r'''
int main(void){
 struct qcom_usb4_dp p={0};struct msm_dp_ctrl_private c={.aux=&p.aux};int cases=0;
 for(int r=0;r<256;r++)for(int s=0;s<16;s++)for(int en=0;en<2;en++){
  reset(r,s);int ret=dp_set_fec_ready(&p,en);
  assert(!ret&&ready==((r&~1)|en)&&status==(s&~3)&&control_calls==1&&clear_calls==1);
  cases++;
 }
 /* Every I/O failure is propagated; nothing follows a failed transaction. */
 for(int r=0;r<256;r++)for(int en=0;en<2;en++){
  reset(r,5);assert(!dp_set_fec_ready(&p,en));int count=operations;
  for(int fail=1;fail<=count;fail++){
   reset(r,5);fail_at=fail;assert(dp_set_fec_ready(&p,en)==-EREMOTEIO);assert(operations==fail&&!control_calls);cases++;
  }
 }
 /* A retained enable flag cannot satisfy a later failed source start. */
 for(int s=0;s<16;s++)for(int signal=0;signal<2;signal++){
  reset(1,s);
  for(int stream=0;stream<3;stream++){
   source_on=false;assert(!dp_set_fec_ready(&p,true));assert(!(status&3));
   emit_fec=signal;attempts=0;int ret=msm_dp_ctrl_fec_start(&c);
   if(signal)assert(!ret&&attempts==1&&source_on&&(status&1));
   else assert(ret==-ETIMEDOUT&&attempts==3&&!source_on);
   source_on=false;status|=3;cases++;
  }
 }
 reset(1,5);stuck_ready=true;assert(!dp_set_fec_ready(&p,true)&&control_calls==1);cases++;
 reset(0,5);stuck_ready=true;assert(dp_set_fec_ready(&p,true)==-EIO&&!control_calls);cases++;
 reset(1,5);stuck_flags=true;assert(dp_set_fec_ready(&p,true)==-EIO&&!control_calls);cases++;
 reset(1,5);stuck_ready=true;assert(dp_set_fec_ready(&p,false)==-EIO&&!control_calls);cases++;
 printf("PASS %d FEC readiness/restart cases\n",cases);
}
'''
variants={'correct':func,'clobber_selection':func.replace('(ready & ~DP_FEC_READY) | ', ''),'skip_ack':func.replace('ret = dp_control(dp, tx, rx);', '(void)tx; (void)rx; (void)dp_control; ret = 0;'),'missing_W1C':func.replace('DP_FEC_DECODE_EN_DETECTED | DP_FEC_DECODE_DIS_DETECTED);','0);',1),'reject_all_status':func.replace('if (status & (DP_FEC_DECODE_EN_DETECTED | DP_FEC_DECODE_DIS_DETECTED))','if (status)'),'ignore_stuck_flags':func.replace('if (status & (DP_FEC_DECODE_EN_DETECTED | DP_FEC_DECODE_DIS_DETECTED))','if (false)')}
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);result={}
 for name,body in variants.items():
  f=p/(name+'.c');exe=p/name;f.write_text(header+body+main)
  subprocess.run(['cc','-include',HARNESS_HEADER,'-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(f),'-o',str(exe)],check=True)
  r=subprocess.run([str(exe)],capture_output=True,text=True)
  if name=='correct':assert r.returncode==0,r.stderr;print(r.stdout.strip());result[name]=r.stdout.strip()
  else:assert body!=func and r.returncode==134,name;result[name]='rejected'
 if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
 print(result)
