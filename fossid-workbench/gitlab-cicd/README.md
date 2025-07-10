# GitLab CI/CD Examples for Workbench

These templates show how to add Workbench to a GitLab CI/CD pipeline.

## About these Examples 
These templates use GitLab CI/CD variables for mapping repositories and branches to Workbench Projects and Scans. 
- Projects are named using the `$CI_PROJECT_PATH` variable.
- Scans are named as `$CI_PROJECT_PATH/$CI_COMMIT_REF_NAME`.

If you prefer, you can map scans to Tags instead of Branches. For more information, read the [Structuring Scans and Projects](https://fossid.atlassian.net/servicedesk/customer/portal/3/article/372965437) Guide in the Support Wiki.

## Prerequisites
To use these examples, you need access to FossID Workbench, a User Account, and the User's API Token.

To run the Workbench Agent container, you need an Image Pull Secret for our Quay Registry. If you don't have one, please [contact FossID Support](https://support.fossid.com) to request one.

## Required Variables
Set these as [CI/CD Variables](https://docs.gitlab.com/ee/ci/variables/) in your GitLab project or group:

- `WORKBENCH_URL` - Your FossID Workbench instance URL
- `WORKBENCH_USER` - Your Workbench username
- `WORKBENCH_TOKEN` - Your Workbench API token  
- `QUAY_USER` - Username for FossID's Quay registry
- `QUAY_TOKEN` - Token for FossID's Quay registry

## Available Workflows

### Scanning Branches on Code Push
These workflows show how to maintain up-to-date reports for a Git Branch by re-scanning the Branch with Delta Scan as code changes are pushed.

- `wb-agent-branch-scan.yml` - runs the Workbench Agent using the container image

The first time these workflows run on a branch, every file will be scanned. As additional changes are pushed, only the delta is analyzed.

### Scanning File Diffs in Merge Requests
These workflows perform differential scans by fetching the source and target branches then isolating only the files that changed before submitting them for analysis.

- `wb-agent-diff.yml` - creates a ZIP of changed files and scans them by uploading code to Workbench.
- `wb-agent-blind-diff.yml` - scans the changed files "blind" - without uploading code to the Workbench.

These workflows use the [Post-Scan Gates Sample Script](https://github.com/fossid-ab/workbench-api-samples/tree/main/post-scan-gates) to demonstrate how a Merge Request can be blocked until findings are addressed.

### Using API Samples
These workflows show other examples from our API Sample Scripts.

- `wb-api-gating.yml` - runs in a Merge Request to ensure the source branch has no outstanding issues. Requires a scan of the source branch to be in Workbench.
- `ort-to-workbench.yml` - an example that runs ORT then uses the [DA Upload Sample Script](https://github.com/fossid-ab/workbench-api-samples/tree/main/import-da) to upload the results into Workbench for viewing.

## Tips for GitLab CI/CD Integration

1. **Use Protected Variables**: Set sensitive variables like tokens as protected and masked in your GitLab project settings.

2. **Optimize for Performance**: Use `delta_only` and `reuse_identifications` options to reduce scan times on frequently updated branches.

3. **Pipeline Rules**: Use GitLab's `rules` keyword to control when jobs run (e.g., only on merge requests, specific branches, etc.).

4. **Artifacts**: Consider using GitLab artifacts to store scan results and reports for later review.

5. **Docker Images**: All examples use the official FossID Workbench Agent container for consistency and reliability. 