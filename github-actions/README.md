# GitHub Actions Examples!

These YAML files show you how to add FossID to your GitHub Actions workflows. 
The following examples are available:

1. toolbox-diffscan.yml - uses the Toolbox DiffScan to compare two REFs during a Pull Request
2. wb-agent-python.yml - a workflow that uses the Workbench Agent to scan as code is pushed to branches
3. wb-agent-container.yml - an implementation of the same Workbench Agent workflow, using the container instead

# Secrets 

We recommend saving the credentials for the Workbench Agent or Diff Scanner as [Encrypted Secrets[(https://docs.github.com/en/actions/security-guides/encrypted-secrets). 

# Structuring Projects and Scans 

Our sample templates use GitHub's Default Environment Variables for naming your Projects and Scans.
- Projects can be named using the $GITHUB_REPOSITORY variable.
- Scans under Projects can be named using the $GITHUB_REPOSITORY/$GITHUB_REF_NAME.

For more information, refer to the [Structuring Scans and Projects](https://fossid.atlassian.net/servicedesk/customer/portal/3/article/372965437) Guide in the Support Wiki.
