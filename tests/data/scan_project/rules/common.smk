import pandas as pd

SAMPLES = ["a", "b"]
FILTER_TAG = "strict" if config.get("strict") else "loose"

def bam(step, suffix=".bam"):
    return f"{step}/{{sample}}{suffix}"

def count_inputs(wildcards):
    inputs = {"bam": bam("aligned").format(sample=wildcards.sample)}
    if config.get("dedup"):
        inputs["bam"] = bam("dedup").format(sample=wildcards.sample)
    return inputs
