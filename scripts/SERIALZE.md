# Job import and export

This example is in Python and based on the hello world example from the Quick-Start guide.

Code snippet for exporting a JobSpec as json:
```
from psij import Export

e = Export()
...
job = make_job()
e.export(obj=job.spec , dest="jobSpec.json")
```

The command line example below shows how to run and submit an exported job 10 times using slurm.
```
python ./psij-consol.py run --job-executor slurm --number-of-jobs 10 jobSpec.json
```

In addition a job can be imported and submitted using the import functionality of PSIJ:
```
from psij import Import
i = Import()
job = psij.Job()
spec = i.load(src="jobSpec.json")
job.spec = spec
```
