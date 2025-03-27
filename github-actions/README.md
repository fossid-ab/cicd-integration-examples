# GitHub Actions Examples!

These YAML files show you how to add FossID to your GitHub Actions workflows. 
The following examples are available:

1. toolbox-diffscan.yml - uses the Toolbox DiffScan to compare two REFs during a Pull Request
2. wb-agent-python.yml - shows how you can set up the Workbench Agent to scan when code is pushed to a branch
3. wb-agent-container.yml - an implementation of the same Workbench Agent workflow, using the container instead

# Secrets 

We recommend saving the credentials for the Workbench Agent or Diff Scanner as [Encrypted Secrets[(https://docs.github.com/en/actions/security-guides/encrypted-secrets). 

# Project and Scan Naming Strategy

For naming your Projects and Scans, we recommend using GitHub Actions’ Default Environment Variables.
- Projects can be named using the GITHUB_REPOSITORY variable.
- Scans under Projects can be named using the GITHUB_HEAD_REF.

For more information, refer to the [Structuring Scans and Projects](https://fossid.atlassian.net/servicedesk/customer/portal/3/article/372965437) Guide in the Support Wiki.
