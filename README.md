# About this Repo
This repo contains templates for various CI/CD systems that help accelerate integrating FossID Workbench and FossID Toolbox in your CI/CD pipelines. This is an ongoing effort by the Customer Success Team to have ready-made examples for various ecosystems. 

Please note these examples are not complete pipelines. They are intended to show only how FossID can be added to your own.

## About the Repo Structure
These examples are divided into folders for FossID Toolbox and FossID Workbench since these are separate tools serving different use cases.

### FossID Workbench
Workbench is a Web Application that provides thorough auditing and report generation capabilities. 

For Workbench, we provide examples using the [Workbench Agent](https://github.com/fossid-ab/workbench-agent) both as a Python script and as a container. Some examples also leverage our [API Sample Scripts](https://github.com/fossid-ab/workbench-api-samples) where it makes sense.

## FossID Toolbox
Toolbox is a scanner that, in a CI/CD context, is primarily used for Diff Scanning. Toolbox does not interact with Workbench; output is shown in the Terminal. 

For Toolbox, we provide examples using the Toolbox Container Image but it can also be invoked as a binary.

# Contributing 
Contributors are welcome! If you have suggestions for improvement please share them with us!

Feel free to raise questions or feature requests in our [Support Portal](https://support.fossid.com)
