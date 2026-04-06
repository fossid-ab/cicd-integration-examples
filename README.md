# About this Repo
This repo has reference templates to help you run FossID Workbench and FossID Toolbox in CI/CD pipelines. This is an ongoing effort to have ready-made examples for various ecosystems. The examples are sorted into folders for the CI/CD platforms they apply to.

Please note these examples are not complete pipelines. They are intended to show only how FossID can be added to your own.

## FossID Workbench Examples
Workbench is a FossID's Web Application that provides auditing and report generation capabilities. 

For Workbench, we provide examples using the [Workbench Agent](https://github.com/fossid-ab/workbench-agent) and the [CE Workbench Agent](https://github.com/fossid-ab/workbench-agent-ce) for various Scanning and Gating Use Cases.

### Prerequisites
To use these examples, you need access to FossID Workbench, a User Account, and the User's API Token.

## FossID Toolbox
Toolbox is a stateless scanner that in a CI/CD pipeline is primarily used for Diff Scanning. Please Note Toolbox does not interact with Workbench; output is shown in the Terminal.

For Toolbox, we provide examples showing how DiffScan find Snippets or Full Files from Open Source Projects or Vulnerable Snippets mapped to CVEs.

### Prerequisites
To use these examples, you need a Token for the FossID Knowledge Base. You will also need a Image Pull Secret for our Quay registry as the Toolbox image is not public. Both can be found in your [Evaluation Portal](https://vault-eu.foss.id/eval) or [Delivery Portal](https://vault-eu.foss.id/delivery).

# Contributing 
This Repo is maintained by the CS Team. Contributors are welcome! If you have ideas or suggestions for improvement please share them with us in our [Support Portal](https://support.fossid.com) or by opening a GitHub Issue in this repo.