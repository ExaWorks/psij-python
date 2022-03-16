# Workflow examples

## Environmental COVID Workflow

Wastewater samples are collected and then concentrated to select for viral particles. RNA is then extracted from the concentrated viral solution. This RNA is prepped for sequencing using an amplicon panel targeting the entire [SARS-CoV-2 genome](https://www.ncbi.nlm.nih.gov/sars-cov-2/), and then sequenced. Resulting sequence files are the input for the pipeline below. The sequences are assembled and reads are mapped against the SARS-CoV-2 reference genome for variant detection.

![image](../web/images/assembly-workflow.svg)

This workflow consists of four major steps or jobs:

1. Sequence mapping
2. Variant calling
3. Quality control and filtering
4. Group and plot results for all samples

The tools are packaged in docker/singularity containers. The job spec documents for the jobs above have the follwoing format:

```
spec = psij.JobSpec()
    spec.executable = 'singularity'
    spec.arguments = ['run' , "-bind" , $directory , $tool , $option ]
    spec.stdout_path = 'log.stdout'
    spec.attributes
```

