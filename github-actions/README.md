# FossID GitHub Actions Examples!

These workflow files show how to add FossID to a GitHub Actions Workflow. 

Examples for both Workbench and Toolbox are provided. The README in the Repo root has a refresher on differences between them if needed.

# FossID Toolbox
For Toolbox, the following examples are provided:
1. `toolbox-diffscan.yml` - uses the Toolbox DiffScan to check for license issues
2. `toolbox-diffscan-vsf.yml` - uses Toolbox DiffScan to check for Vulnerable Code Snippets
3. `toolbox-diffscan-ignore-projects.yml` - uses Toolbox DiffScan with an Ignore Projects List to exclude results from specified repos

# FossID Workbench
For Workbench, the following examples are provided:
1. `wb-agent-ce-scan-gate-report.yml` - on push to a branch, scan the branch, check compliance gates, download reports
2. `wb-agent-ce-diffscan.yml` - an example of how you can scan only the files changed in a PR
3. `wb-agent-python.yml` - an example that runs the Workbench Agent as a Python script instead of a container
4. `wb-agent-ce-import-ort-results.yml` - runs ORT then uploads the results to Workbench for reporting

# Combo Workflow
You can also use both for more complex workflows! For example:
1. `toolbox-workbench-pr-diffscan.yml` - scans with Toolbox first, then with Workbench if Toolbox found something

## Reusing Workflows

The `reusable-workflows` folder has sample workflows showing how you can implement these using GitHub Actions Reusable Workflows.

## Required Secrets 

We recommend saving the secrets for Toolbox as [Encrypted Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets) - this is illustrated in the examples.