# Workflow examples

## PDF to Cloud Image

Input: PDF
Output: png

Scripts:
- pdftotext
- wordcloud_cli.py
- pdf2wordcloud.sh

Steps:

![image](../web/images/wordcloud-workflow.svg)

1. extract text from PDF file

    `pdftotext INPUT.pdf OUTPUT.txt`

2. create image from text

    `wordcloud_cli.py --text OUTPUT.txt --imagefile IMAGE.png`

Example:

```
import psij

### Basic config and inputs ###
jex = psij.JobExecutor.get_instance('local')
pdfFile = "example.pdf"     # input file
pngFile = "worcloud.png"    # output file

### Specs for tools ###


def make_pdf2text_spec(input=None, output=None):
    '''
    :param input: path to input file
    :param output: name for output file
    '''
    spec = psij.JobSpec()
    spec.executable = 'pdftotext'
    spec.arguments = [input, output]
    spec.stdout_path = 'pdftotext.stdout'
    spec.stderr_path = 'pdftotext.stderr'
    spec.attributes.set_custom_attribute("DEMO", "DEMO")

    return spec


def make_text2wordcloud_spec(input, output):
    spec = psij.JobSpec()
    spec.executable = 'wordcloud_cli'
    spec.arguments = ["--text", input, "--imagefile", output]
    spec.stdout_path = 'wordcloud.stdout'
    spec.stderr_path = 'wordcloud.stderr'
    return spec

### Make simple job from spec ###


def make_job(spec, attributes):
    job = psij.Job()
    job.spec = spec
    return job


# Create job spec
pdf2textSpec = make_pdf2text_spec(pdfFile, "words.txt")
text2wordcloudSpec = make_text2wordcloud_spec("words.txt", pngFile)

# Create jobs from spec
pdf2textJob = make_job(pdf2textSpec, None)
text2wordcloudJob = make_job(text2wordcloudSpec, None)

for j in [pdf2textJob, text2wordcloudJob]:
    jex.submit(j)
    j.wait()

```


The tools used in the example above can be easily installed in a docker container:

```
FROM ubuntu:latest
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y \
  poppler-utils \
  python3-pip
RUN pip install wordcloud
```

## Executing a singularity conatiner

We will run the PDF2Wordcloud example in a container. We will use the docker conatiner described above and execute it with singularity.

```
import os
import psij


jex = psij.JobExecutor.get_instance('local')
pdfFile = "example.pdf"
pngFile = "worcloud.png"
image = "docker://wilke/pdf2wordcloud:psij"


def make_pdf2text_spec(input=None, output=None):
    '''
    :param input: path to input file
    :param output: name for output file
    '''
    spec = psij.JobSpec()
    spec.executable = 'pdftotext'
    spec.arguments = [input, output]
    spec.stdout_path = 'pdftotext.stdout'
    spec.stderr_path = 'pdftotext.stderr'
    spec.attributes.set_custom_attribute("DEMO", "DEMO")

    return spec


def make_text2wordcloud_spec(input, output):
    spec = psij.JobSpec()
    spec.executable = 'wordcloud_cli'
    spec.arguments = ["--text", input, "--imagefile", output]
    spec.stdout_path = 'wordcloud.stdout'
    spec.stderr_path = 'wordcloud.stderr'
    return spec


def make_singularity_spec(image=None,
                          bind_input=[],
                          bind_output=[],
                          command='',
                          options=[]
                          ):
    '''
    :param image: path to image file
    :param bind_input: List of input paths
    :param bind_output: :ist of output paths
    :param command: name of script/command to be executed
    :param options: command line options for command
    '''
    spec = psij.JobSpec()
    spec.executable = 'singularity'
    spec.stdout_path = 'singularity.' + command + '.stdout'
    spec.stderr_path = 'singularity.' + command + '.stderr'
    bind = []
    for f in bind_input:
        if f:
            d = os.path.abspath(f)
            bind += ["--bind", f"{f}:{d}"]
    for f in bind_output:
        if f:
            # missing, if f does not exists create f
            d = os.path.abspath(f)
            bind += ["--bind", f"{f}:{d}"]
    spec.arguments = ['run'] + bind + [image, command] + options

    return spec


def make_job(spec, attributes):
    job = psij.Job()
    job.spec = spec
    return job


# Create job spec
pdf2textSpec = make_pdf2text_spec(pdfFile, "words.txt")
text2wordcloudSpec = make_text2wordcloud_spec("words.txt", pngFile)

pdf2textSingularitySpec = make_singularity_spec(image=image,
                                                bind_input=[pdfFile],
                                                bind_output=["words.singularity.txt"],
                                                command="pdftotext",
                                                options=[pdfFile, "words.singularity.txt"])
text2wordcloudSingularitySpec = make_singularity_spec(image=image,
                                                      bind_input=["words.singularity.txt"],
                                                      bind_output=[pngFile],
                                                      command="pdftotext",
                                                      options=["--text", "words.singularity.txt", "--imagefile", pngFile])


# Create jobs from spec
pdf2textJob = make_job(pdf2textSpec, None)
text2wordcloudJob = make_job(text2wordcloudSpec, None)

for j in [make_job(pdf2textSingularitySpec, None), make_job(text2wordcloudSingularitySpec, None)]:
    jex.submit(j)
    j.wait()
```


<!-- ## Environmental COVID Workflow

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
 -->
