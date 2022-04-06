# Workflow examples

1. [PDF to Wordcloud](#pdf-to-wordcloud-image)
2. [Executing a singularity container](#executing-a-singularity-conatiner)
3. [Submitting a MPI job](#executing-an-mpi-job)

## PDF to Wordcloud Image

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

We will run the PDF2Wordcloud example in a container. We will use the docker conatiner described above and execute it with singularity. In this case the spec defines the execution of a container with singularity. The actual command line tool is passed as an optional argument after all requiered singularity options.

```
...

def make_singularity_spec(image=None,
                          bind_input=[],
                          bind_output=[],
                          command='',
                          options=[]
                          ):
    '''
    :param image: path to image file
    :param bind_input: List of input paths
    :param bind_output: :List of output paths
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


...


# Create job spec

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

....

# Create jobs from spec
for j in [make_job(pdf2textSingularitySpec, None), make_job(text2wordcloudSingularitySpec, None)]:
    jex.submit(j)
    j.wait()
```

## Executing an MPI job

In this example we demonstrate how to wrap and execute an mpi hello world job with PSI/J. The base mpi command is `mpiexec -n 36 -ppn 36 echo Hello world`. This example is introducing the concept of a [job launcher](https://exaworks.org/psi-j-python/docs/programming.html#launchers), in this case **mpi**, e.g. `job.spec.launcher = "mpi"`.
