# Scripts

This directory contains helper scripts and the console for PSIJ.

## psij-console

The console takes an exported JobSpec document and either validates or executes it.


```
usage: psij-consol [-h] [-v] [--debug] {validate,run} ...

positional arguments:
  {validate,run}  Subcommands
    validate      validate JobSpec file
    run           execute JobSpec file

optional arguments:
  -h, --help      show this help message and exit
  -v, --verbose   print detailed information
  --debug         print debug information
```

