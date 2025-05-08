# GitHub Actions Example Reusable Workflows

This directory contains example [GitHub Actions Reusable Workflows](https://docs.github.com/en/actions/sharing-automations/reusing-workflows) for the Workbench Agent and Toolbox Diffscan.

## Setting Up Secrets

It's recommended to set up all required secrets at the organization level to make them available to all repositories using these workflows.

## Customization

The called workflow files contain all the necessary logic to run the scans, while the caller workflows allow you to configure the scan process for each repository. For a complete list of supported parameters and their descriptions, please refer to the [FossID Workbench Agent Repository](https://github.com/fossid-ab/workbench-agent).

