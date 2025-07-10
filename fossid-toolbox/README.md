# About FossID Toolbox
FossID Toolbox is a scanner that, in a CI/CD context, is primarily used for Diff Scanning. These examples show how you can use DiffScan to find:
- Snippets or Full Files from Open Source Projects
- Vulnerable Snippets of Open Source mapped to CVEs

Please Note: Toolbox does not interact with Workbench; output is shown in the Terminal. 

## Prerequisites
To use these examples, you need a Scan Token for the FossID Knowledge Base. You can retrieve the token from your [Evaluation Portal](https://vault-eu.foss.id/eval) or [Delivery Portal](https://vault-eu.foss.id/delivery).

These examples run Toolbox as a container. The image is not public, so you'll need an Image Pull Secret for our Quay Registry. If you don't have one, reach out to your account team or contact us through the [FossID Support Portal](https://support.fossid.com) to request one.

## Additional Reading
To learn more about Toolbox, including functionality not related to Diff Scanning, read the [Toolbox User Guide](https://eval-eu.foss.id/cs-demo/help/en/toolbox/user_guide.html).