rule dedup:
    input: bam("aligned")
    output: bam("dedup")
    shell: "dedup ..."
