rule all:
    input: "test_only.txt"

rule make_test_data:
    output: "test_only.txt"
    shell: "touch {output}"
