# About this Repo
This repo has reference templates to accelerate integrating FossID Workbench and FossID Toolbox into CI/CD pipelines. This is an ongoing effort to have ready-made examples for various ecosystems. 

Please note these examples are not complete pipelines. They are intended to show only how FossID can be added to your own.

## About the Repo Structure
The examples are separated into folders for FossID Toolbox and FossID Workbench as these are separate tools serving different use cases.

### FossID Workbench
Workbench is a Web Application that provides thorough auditing and report generation capabilities. 

For Workbench, we provide examples using the [Workbench Agent](https://github.com/fossid-ab/workbench-agent) both as a Python script and as a container. Some examples also leverage the [API Sample Scripts](https://github.com/fossid-ab/workbench-api-samples) where it makes sense.

### FossID Toolbox
Toolbox is how Workbench scans under the covers. In a CI/CD context, its primary use case is Diff Scanning. When used in this way, Toolbox does not interact with Workbench; output is shown in the Terminal. 

For Toolbox, we provide examples using the Toolbox Container Image.

# Contributing 
Contributors are welcome! If you have ideas or suggestions for improvement please share them with us!

Feel free to raise questions or feature requests in our [Support Portal](https://support.fossid.com)
