# GitHub Actions Example Reusable Workflows

This directory contains example [GitHub Actions Reusable Workflows](https://docs.github.com/en/actions/sharing-automations/reusing-workflows) for Toolbox Diffscan.

## Setting Up Secrets
It's recommended to set up all required secrets at the organization level to make them available to all repositories using these workflows.

## Customization
The called workflows contain the necessary logic to run the scans, while the caller workflows allow you to fine-tune the scan for each repository. 

