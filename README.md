## create_and_populate_library.py

A script that can be used to create a data library in Galaxy and populate it
with files. The script can be run multiple times and it will create and upload
any files not already present in the library.

Run the script with

```
python create_and_populate_library.py -g http://localhost:8080 -a d018e83a92c45826f6e1a273f74f7fb4 -l 'Common data' -d 'Desc' -m manifest.yaml
```

The data manifest file contains the list of files to ingest into the library
and needs to be in the following format. The argument for this file can be
provided as a path or a URL that points to a file.

```
datasets:
  - name: RefSeq_reference_DSv2.gtf
    url: 'https://ea1-usegvl-org-gvl-data.s3.amazonaws.com/GTFs/RefSeq_reference_DSv2.gtf'
    folder_name: GTFs
    folder_description: A collection of GTF files
    type: gtf
    dbkey: mm10
  - name: 1.fasta
    url: 'https://ea1-usegvl-org-gvl-data.s3.amazonaws.com/1.fasta'
    folder_name: FASTA
    folder_description: A collection of transcriptome files
    type: fasta
```
