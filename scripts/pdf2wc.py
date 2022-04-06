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
