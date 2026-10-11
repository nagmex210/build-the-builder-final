cd /home/ubuntu/btb/repo
python3 btb/fast_eval.py c591c751-dc19-4660-9955-f9a4d750213d --brief A --reps 2 --style random --out runs/b6/merge/fe-A.json > runs/b6/merge/fe-A.log 2>&1 &
python3 btb/fast_eval.py 0e92e0fa-2e50-4314-8434-33760d22f246 --brief B --reps 2 --style random --out runs/b6/merge/fe-B.json > runs/b6/merge/fe-B.log 2>&1 &
python3 btb/fast_eval.py 63f0e252-1681-4981-95d9-7bd18b847389 --brief A --reps 2 --style random --out runs/b6/merge/fe-rA.json > runs/b6/merge/fe-rA.log 2>&1 &
python3 btb/fast_eval.py e99b473c-2df6-4d05-927d-5b0085543563 --brief B --reps 2 --style random --out runs/b6/merge/fe-rB.json > runs/b6/merge/fe-rB.log 2>&1 &
python3 btb/fast_eval.py 3f1e0c2c-d777-4204-bbf2-39eac684c2a5 --cases btb/brief_c/cases-c.json --bank $(cat btb/brief_c/BANK_URL) --reps 1 --out runs/b6/merge/fe-C.json > runs/b6/merge/fe-C.log 2>&1 &
python3 btb/fast_eval.py 3f1e0c2c-d777-4204-bbf2-39eac684c2a5 --cases btb/brief_c/cases-c.json --bank $(cat btb/brief_c/BANK_URL) --reps 1 --style adversarial --out runs/b6/merge/fe-C-adv.json > runs/b6/merge/fe-C-adv.log 2>&1 &
( python3 tools/run_cases.py d7b2b782-a1c2-42ce-b004-ab865e0186de --brief A --reps 2 > runs/b6/official-A.txt 2>&1; python3 tools/run_cases.py b304e838-1091-40b6-aa62-a0cd00da1dc1 --brief A --reps 1 > runs/b6/official-rA.txt 2>&1 ) &
( python3 btb/official_ws2.py main-B --brief B --reps 2 > runs/b6/official-B.txt 2>&1; python3 btb/official_ws2.py main-rB --brief B --reps 1 > runs/b6/official-rB.txt 2>&1 ) &
wait
