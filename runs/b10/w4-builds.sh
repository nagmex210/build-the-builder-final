#!/bin/bash
# usage: w4-builds.sh <round>  -- 3 builds each of A, B, rB, C in parallel (slots w4-<brief>-<round><i>)
cd /home/ubuntu/btb/wt4
R=$1
for i in 1 2 3; do
  python3 builder/build.py --slot w4-A-$R$i --tools tools/openapi.json briefs/brief-a.md > runs/b10/w4-A-$R$i.build.log 2>&1 &
  python3 builder/build.py --slot w4-B-$R$i --tools tools/openapi.json briefs/brief-a.md briefs/brief-b.md > runs/b10/w4-B-$R$i.build.log 2>&1 &
  python3 builder/build.py --slot w4-rB-$R$i --tools tools/openapi.json btb/briefs_raw/brief-a-raw.md btb/briefs_raw/brief-b-raw.md > runs/b10/w4-rB-$R$i.build.log 2>&1 &
  python3 builder/build.py --slot w4-C-$R$i --tools btb/brief_c/openapi-c.json btb/brief_c/brief-c.md > runs/b10/w4-C-$R$i.build.log 2>&1 &
done
wait
echo ALLDONE > runs/b10/w4-round$R.done
