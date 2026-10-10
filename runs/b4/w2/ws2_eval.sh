#!/bin/bash
# usage: ws2_eval.sh <slot> <brief-letter> <out.json> : copy slot's ws1 workflow to ws2 (slot ev-<slot>) and fast_eval it there
cd /home/ubuntu/btb/wt2
K2=$(aws ssm get-parameter --region eu-central-1 --name /btb/freya_api_key_2 --with-decryption --query Parameter.Value --output text)
WID=$(python3 - "$1" <<'PY'
import json,sys,os,freya
slot=sys.argv[1]
st=json.load(open('.freya-agents.json'))[slot]
wf=freya.api("GET", f"/api/v2/workflow/{st['workflow_id']}", workspaceId=freya.workspace_id())["workflow"]["workflow"]
freya.HEADERS["Authorization"]="Bearer "+os.popen("aws ssm get-parameter --region eu-central-1 --name /btb/freya_api_key_2 --with-decryption --query Parameter.Value --output text").read().strip()
freya._ws=None; os.environ.pop("FREYA_WORKSPACE_ID",None)
print(freya.save_workflow("ev-"+slot, wf, state_file=".freya-agents-ws2.json")["workflow_id"])
PY
)
echo "ws2 $1 -> $WID"
FREYA_API_KEY=$K2 FREYA_WORKSPACE_ID= python3 btb/fast_eval.py $WID --brief $2 --reps 2 --style random --out $3
