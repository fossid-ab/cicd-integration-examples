# FossID Toolbox: GitHub Actions Examples!

These workflow files show how to add FossID Toolbox to a Pull Request workflow. In them, the `diffscan` command is used to compare the HEAD and BASE refs to highlight newly introduced open source licenses or vulnerable code snippets. 

The following examples are available:

1. `toolbox-diffscan.yml` - uses the Toolbox DiffScan to check for license issues
2. `toolbox-diffscan-vsf.yml` - uses Toolbox DiffScan to check for Vulnerable Code Snippets

## Reusing Workflows

The `reusable-workflows` folder has workflows showing how you can implement this using GitHub Actions Reusable Workflows.

## Required Secrets 

We recommend saving the secrets for Toolbox as [Encrypted Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets) - this is illustrated in the examples.