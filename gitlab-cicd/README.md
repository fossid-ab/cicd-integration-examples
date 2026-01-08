# FossID Toolbox: GitLab CI/CD Examples

These workflow files show how to add FossID Toolbox to a GitLab CI/CD pipeline. The `diffscan` command is used to compare source and target branches in merge requests to highlight newly introduced open source licenses or vulnerable code snippets.

## Prerequisites

To use these examples, you need a Token for the FossID Knowledge Base. You can retrieve the token from your [Evaluation Portal](https://vault-eu.foss.id/eval) or [Delivery Portal](https://vault-eu.foss.id/delivery).

These examples run Toolbox as a container. The image is not public, so you'll need an Image Pull Secret for our Quay Registry. If you don't have one, reach out to your account team or contact us through the [FossID Support Portal](https://support.fossid.com) to request one.

## Required Variables

Set these as [CI/CD Variables](https://docs.gitlab.com/ee/ci/variables/) in your GitLab project or group:

- `FOSSID_HOST` - Your FossID Knowledge Base URL
- `FOSSID_TOKEN` - Your FossID Knowledge Base API token
- `QUAY_USER` - Username for FossID's Quay registry (optional if using public runners)
- `QUAY_TOKEN` - Token for FossID's Quay registry (optional if using public runners)

## Available Workflows

### License Scanning
- `toolbox-diffscan.yml` - uses the Toolbox DiffScan to check for license issues in merge requests

### Vulnerability Scanning
- `toolbox-diffscan-vsf.yml` - uses Toolbox DiffScan to check for Vulnerable Code Snippets (VSF) in merge requests

## Additional Reading

To learn more about Toolbox, including functionality not related to Diff Scanning, read the [Toolbox User Guide](https://eval-eu.foss.id/cs-demo/help/en/toolbox/user_guide.html).

Please Note: Toolbox does not interact with Workbench; output is shown in the pipeline logs and terminal.
