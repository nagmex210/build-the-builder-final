cd /home/ubuntu/btb/repo
while kill -0 193189 2>/dev/null; do sleep 10; done
python3 tools/run_cases.py bce0c1bc-a68b-436e-a37b-88db6b717c99 --brief B --reps 2 > runs/b8/official-B.txt 2>&1
python3 tools/run_cases.py 33aaaf4a-3519-46f4-8ef1-2aa95ec80014 --brief B --reps 1 > runs/b8/official-rB.txt 2>&1
python3 tools/run_cases.py b304e838-1091-40b6-aa62-a0cd00da1dc1 --brief A --reps 1 > runs/b8/official-rA.txt 2>&1
