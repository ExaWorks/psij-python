import os
import psij

jex = psij.JobExecutor.get_instance('local')

N = 1  # number of jobs to run

pdfFile = "example.pdf"
pngFile = "worcloud.png"
image = "docker://exaworks/pdf2wordcloud:demo"


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
