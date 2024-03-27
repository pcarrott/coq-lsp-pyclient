# CoqPyt

Interact with Coq files and navigate through your proofs using our Python client for [coq-lsp](https://github.com/ejgallego/coq-lsp).

Execute Coq files, retrieve the generated context and edit proofs through insertion and removal of steps.

## Installation

[coq-lsp](https://github.com/ejgallego/coq-lsp) must be installed on version >= 0.1.7. Follow the installation instructions provided [here](https://github.com/ejgallego/coq-lsp#%EF%B8%8F-installation).

```bash
pip install -r requirements.txt
```

```bash
python -m pip install -e .
```

## Usage

Import classes from the ``coqpyt`` package.

<!-- embedme examples/readme.py#L3-L5 -->
```py
from coqpyt.coq.structs import TermType
from coqpyt.coq.base_file import CoqFile
from coqpyt.coq.proof_file import ProofFile
```

Create a CoqFile object, execute the file and extract the generated context.

<!-- embedme examples/readme.py#L7-L34 -->
```py
# Open Coq file
with CoqFile(os.path.join(os.getcwd(), "examples/readme.v")) as coq_file:
    coq_file.exec(nsteps=2)
    # Get all terms defined until now
    print("Number of terms:", len(coq_file.context.terms))
    # Filter by Tactics
    print(
        "Number of tactics:",
        len(
            list(
                filter(
                    lambda term: term.type == TermType.TACTIC,
                    coq_file.context.terms.values(),
                )
            )
        ),
    )

    # Save compiled file
    coq_file.save_vo()
    print("Compiled file exists:", os.path.exists("examples/readme.vo"))
    os.remove("examples/readme.vo")

    # Run remaining file
    coq_file.run()
    print("Checked:", coq_file.checked)
    # Get all terms defined until now
    print("Number of terms:", len(coq_file.context.terms))
```

Create a ProofFile object (a CoqFile instance) and interact with the proofs.

<!-- embedme examples/readme.py#L36-L73 -->
```py
# Open Proof file
with ProofFile(os.path.join(os.getcwd(), "examples/readme.v")) as proof_file:
    # Enter proof
    proof_file.exec(nsteps=4)
    print("In proof:", proof_file.in_proof)
    # Get current goals
    print(proof_file.current_goals)

    # Run remaining file
    proof_file.run()
    # Number of proofs in the file
    print("Number of proofs:", len(proof_file.proofs))
    print("Proof:", proof_file.proofs[0].text)

    # Print steps of proof
    for step in proof_file.proofs[0].steps:
        print(step.text, end="")
    print()

    # Get the context used in the third step
    print(proof_file.proofs[0].steps[2].context)
    # Print the goals in the third step
    print(proof_file.proofs[0].steps[2].goals)

    # Print number of terms in context
    print("Number of terms:", len(proof_file.context.terms))
    # Filter for Notations only
    print(
        "Number of notations:",
        len(
            list(
                filter(
                    lambda term: term.type == TermType.NOTATION,
                    proof_file.context.terms.values(),
                )
            )
        ),
    )
```

## Tests

To run the tests for CoqPyt go to the folder ``coqpyt`` and run:
```bash
pytest tests -s
```

## Contributing

Pull requests are welcome. 

For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Credits

Special thanks to the developers of the [pylspclient](https://github.com/yeger00/pylspclient) project, which served as the initial template for CoqPyt. Additionally, we express our gratitude to Kyle Thompson (@rkthomps) for his precious feedback, which has greatly contributed to the refinement of CoqPyt.

## License

[MIT](https://choosealicense.com/licenses/mit/)