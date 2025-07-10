# GitHub Actions Examples!

These YAML files show you how to add FossID to your GitHub Actions workflows. 
The following examples are available:

1. toolbox-diffscan.yml - uses the Toolbox DiffScan to compare two REFs during a Pull Request
2. toolbox-diffscan-vsf.yml - uses Toolbox DiffScan to check for Vulnerable Code Snippets
3. wb-agent-python.yml - a workflow that uses the Workbench Agent to scan as code is pushed to branches
4. wb-agent-container.yml - an implementation of the same Workbench Agent workflow, using the container instead
5. wb-api-gating.yml - uses the [Post-Scan Gates Sample Script](https://github.com/fossid-ab/workbench-api-samples/tree/main/post-scan-gates) to show a blocking pull request check.
6. ort-to-workbench.yml - shows how you can run the ORT GitHub Action then use the [DA Upload Sample Script](https://github.com/fossid-ab/workbench-api-samples/tree/main/import-da) to upload its results into Workbench for viewing and reporting.
7. wb-agent-blind-diff.yml - performs differential scanning on pull requests by analyzing only the files that have changed between the base and head branches, using the Workbench Agent with blind scan mode and post-scan gate evaluation.
8. wb-agent-diff.yml - performs differential scanning on pull requests by analyzing only the files that have changed between the base and head branches, using the Workbench Agent with post-scan gate evaluation.

# Secrets 

We recommend saving the credentials for the Workbench Agent or Diff Scanner as [Encrypted Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets) then adding them to the `env` for the GitHub Actions run. 

# Structuring Projects and Scans 

Our sample templates use GitHub's Default Environment Variables for naming your Projects and Scans.
- Projects can be named using the $GITHUB_REPOSITORY variable.
- Scans under Projects can be named using the $GITHUB_REPOSITORY/$GITHUB_REF_NAME.

For more information, refer to the [Structuring Scans and Projects](https://fossid.atlassian.net/servicedesk/customer/portal/3/article/372965437) Guide in the Support Wiki.
