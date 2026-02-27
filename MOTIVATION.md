# Motivation - Open-Source LLMs for Offensive Cybersecurity

## The Problem

Modern cybersecurity professionals face a significant dilemma. As the industry evolves, red teamers increasingly need AI to streamline workflows and keep up with evolving threats. However, commercial LLMs like ChatGPT are heavily restricted by safety filters, frequently refusing to assist with legitimate security testing tasks. Furthermore, feeding sensitive information like log files or proprietary code to commercial AI providers poses a significant security and data privacy risk.

While open-source AI models offer a better alternative, a new problem arises: operating these models requires massive GPU power that most professionals lack locally. Renting cloud infrastructure (like AWS) solves this hardware roadblock but introduces high costs if servers remain active.

Even open-source models - including those explicitly fine-tuned for cybersecurity - retain residual safety alignments inherited from their foundational base models. These hidden guardrails can still cause them to refuse highly explicit offensive tasks.

## What This Project Does

This project provides a complete engineering and research solution across three areas:

1. **Secure, Affordable Infrastructure** - An automated, dispose-on-demand cloud laboratory on AWS that allows professionals to securely and affordably host open-source AI. Servers are created when needed and destroyed when finished - you only pay for what you use, and all data is wiped on shutdown.

2. **Automated Benchmarking** - A benchmarking suite that programmatically evaluates open-source models (including standard and cybersecurity-specialised models) across a gradient of cybersecurity tasks. Prompts deliberately range from indirect, contextual assistance to explicit offensive commands designed to trigger refusal mechanisms. An automated judge scores every response for refusal behaviour, technical accuracy, practical utility, and completeness.

3. **Practical Validation** - The winning model is deployed in a private web interface within the cloud lab and used for authorised red teaming case studies, demonstrating real-world usefulness in an isolated environment.

## Ethical Consideration

This research follows the **Open Science** principle. By using only open-source models and authorised red-teaming environments, we are quantifying the risk that already exists - adversaries are already doing this. We are providing the defensive community with the tools needed to understand and stay ahead of these threats. All testing is conducted in isolated, private environments with no external exposure.