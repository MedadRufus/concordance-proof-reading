# Concordance Proof Reading Application

This application is used to convert a manaully proofread and edited concordance, that was originally OCR'ed from a
printed concordance, into a html page which is easy to double check. The input is in the ODT file format.

The key features are:
1. All bible verse references are hyperlinks to Bible Gateway verses
2. Also, on hover over the reference, the full verse appears at the tool tip
3. References to non-existant verses appear as as "[REF NOT FOUND]" to make it easy to identify

The hover verses are taken from https://github.com/farskipper/kjv which has the whole KJV bible in a JSON format.

## HTML View

This is how the html output looks like:
![](docs/demo.png)

## Deployment
This application is meant to be deployed via cPanel Python App feature. See [DEPLOY.md](DEPLOY.md)
for details.

## Dev

All code must pass the CI checks.

You must autoformat your code with:

```sh
black .
isort .
```

Then verify that all Pylint passes with no warnings/errors:

```sh
pylint $(git ls-files '*.py')
```

Run all unittests with:

```sh
pytest --cov=.
```


# Steps for transcribing with Deep Seek
0. Generate the jpeg files of each column by running `python3 combine_pages_batches.py`. Adjust the starting page number in the last line. Images will be output to [individual_pages](individual_pages)
1. Add the text to the suitable file in [deepseek_output](deepseek_output)
2. run `python3 fix_trailing_spaces.py`
3. run `python3 normalize_deepseek_files.py`
4. run `python3 combine_ai_output.py`. Output will be in [combined_output](combined_output)
6. run `python3 add_hyperlinks_md.py`. Output will be [output/concordance.html](output/concordance.html).
