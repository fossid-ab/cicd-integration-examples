# GitHub Actions Examples!

These templates show how to add Workbench to a GitHub Actions workflow. 

## About these Examples 
These templates use Environment Variables for mapping repositories and branches to Workbench Projects and Scans. 
- Projects are named using the `$GITHUB_REPOSITORY` variable.
- Scans are named as `$GITHUB_REPOSITORY/$GITHUB_REF_NAME`.

If you prefer, you can map scans to Tags instead of Branches. For more information, read the [Structuring Scans and Projects](https://fossid.atlassian.net/servicedesk/customer/portal/3/article/372965437) Guide in the Support Wiki.

### Scanning Branches on Code Push
These workflows show how to maintain up-to-date reports for a Git Branch by re-scanning the Branch with Delta Scan as code changes are pushed.

- `wb-agent-python.yml` - runs the Workbench Agent using Python
- `wb-agent-container.yml` - runs the Workbench Agent container

The first time these workflows run, every file will be scanned. As additional changes are pushed, only the delta is analyzed.

### Scanning File Diffs in Pull Requests
These workflows perform differential scans by fetching the HEAD and BASE branches for a Pull Request and running Git commands to isolate only the files that changed before submitting them for analysis.

- `wb-agent-diff.yml` - creates a ZIP of changed files and scans them by uploading code to Workbench.
- `wb-agent-blind-diff.yml` - scans the changed files "blind" - without uploading code to the Workbench.

These workflows use the [Post-Scan Gates Sample Script](https://github.com/fossid-ab/workbench-api-samples/tree/main/post-scan-gates) to demonstrate how a Pull Request can be blocked until findings are addressed. 

### Using API Samples
These workflows show other examples from our API Sample Scripts.

- `wb-api-gating.yml` - runs in a Pull Request to ensure the HEAD branch has no outstanding issues. Requires a scan of the HEAD branch to be in Workbench. 
- `ort-to-workbench.yml` - an example that runs the ORT GitHub Action then uses the [DA Upload Sample Script](https://github.com/fossid-ab/workbench-api-samples/tree/main/import-da) to upload the results into Workbench for viewing.
