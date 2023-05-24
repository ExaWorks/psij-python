import textwrap


labs = {
    "LLNL": {
        "resources": True,
        "arguments": True,
        "stdout": True,
        "stderr": True,
    },
    "ANL": {
        "resources": True,
        "arguments": True,
        "attributes": True,
    },
    "ORNL": {
        "arguments": True,
    },
}

job_spec = {
    "resources": """
            resources=ResourceSpecV1( 
                process_count= <SPECIFY PROCESS COUNT HERE>,
                node_count= <SPECIFY NODE COUNT HERE>,
                processes_per_node= <SPECIFY PROCESS COUNT HERE>,
                cpu_cores_per_process= <SPECIFY CPU CORE COUNT HERE>
                ),
    """,
    "arguments": """
            arguments= ["<SPECIFY>", "<ARGS>", "<HERE>", ...], # NOTE: must be list of strings
    """,
    "attributes": """
            attributes=JobAttributes(
                queue_name= "<SPECIFY PROJECT QUEUE/BANK HERE>"
            ),
    """,
    "stdout": """
            stdout_path= "<SPECIFY PATH/TO/STDOUT>", 
    """,
    "stderr": """
            stderr_path= "<SPECIFY PATH/TO/STDERR>"
    """,
}

def build_job_spec(lab: str) -> str:
    res: list[str] = []
    lab_data = labs[lab]
    for lab_build_req, build_req_descr in job_spec.items():
        if lab_data.get(lab_build_req, False):
            res.append(build_req_descr)
    return "".join(res)


def generate_example(res: str) -> str:
    return textwrap.dedent(f"""
    job = Job(
        JobSpec(
            executable="/bin/sleep",
            {res}
        )
    )
    executor.submit(job)

    print(job.status)
    job.wait()
    print(job.status)
    """)


if __name__ == "__main__":
    possible_choices = dict(
        zip(
            list(range(len(labs))),
            labs.keys()
        )
    )

    print("Choose Lab")
    print("\n".join([f'[{k}] {v}' for (k,v) in possible_choices.items()]))
    print()

    chosen_lab = int(input("Choose lab: "))
    chosen_lab = possible_choices.get(chosen_lab, "LLNL")

    print(f"{chosen_lab.upper()} needs the following specs to build correctly:")
    print("\n".join(labs[chosen_lab].keys()))
    print()

    basic_setup = textwrap.dedent("""
    from psij import Job, JobExecutor, JobSpec, ResourceSpecV1, JobAttributes

    executor = JobExecutor.get_instance("<local/cobalt/lsf/pbs/slurm>")
    """)

    print(f"Here is a quickstart example for {chosen_lab}:")
    print("============")
    spec = build_job_spec(chosen_lab)
    sample = generate_example(spec)
    print(basic_setup, end="")
    print(sample)

    file_ = "main.py"
    with open(file_, "w+") as f:
        f.write(basic_setup)
        f.write(sample)

    print("============")
    print(f"\nWrote sample to ./{file_}\n")
