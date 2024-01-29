import pytest

from coqpyt.coq.lsp.structs import *
from coqpyt.coq.exceptions import *
from coqpyt.coq.changes import *

from utility import *


class TestProofValidFile(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_valid.v")

    def test_delete_and_add(self):
        proof_file = self.proof_file
        proof_file.delete_step(6)

        test_proofs = get_test_proofs("tests/proof_file/expected/valid_file.yml")
        test_proofs["proofs"][0]["steps"].pop(1)
        for i, step in enumerate(test_proofs["proofs"][0]["steps"]):
            if i != 0:
                step["goals"]["position"]["line"] -= 1
            if i != len(test_proofs["proofs"][0]["steps"]) - 1:
                step["goals"]["goals"]["goals"][0]["hyps"] = []
                step["goals"]["goals"]["goals"][0]["ty"] = "∀ n : nat, 0 + n = n"
        check_proof(test_proofs["proofs"][0], proof_file.proofs[0])

        proof_file.add_step(5, "\n      intros n.")

        test_proofs = get_test_proofs("tests/proof_file/expected/valid_file.yml")
        check_proof(test_proofs["proofs"][0], proof_file.proofs[0])

        # Check if context is changed correctly
        proof_file.add_step(7, "\n      Print minus.")
        step = {
            "text": "\n      Print minus.",
            "goals": {
                "goals": {
                    "goals": [
                        {"hyps": [{"names": ["n"], "ty": "nat"}], "ty": "0 + n = n"}
                    ]
                },
                "position": {"line": 12, "character": 6},
            },
            "context": [
                {
                    "text": "Notation minus := Nat.sub (only parsing).",
                    "type": "NOTATION",
                }
            ],
        }
        add_step_defaults(step)
        test_proofs["proofs"][0]["steps"].insert(3, step)
        for i, step in enumerate(test_proofs["proofs"][0]["steps"][4:]):
            step["goals"]["position"]["line"] += 1
        check_proof(test_proofs["proofs"][0], proof_file.proofs[0])

        # Add step in beginning of proof
        proof_file.add_step(26, "\n    Print plus.")
        assert proof_file.steps[27].text == "\n    Print plus."

        # Add step to end of proof
        proof_file.add_step(31, "\n    Print plus.")
        assert proof_file.steps[32].text == "\n    Print plus."

        # Delete step in beginning of proof
        proof_file.delete_step(27)
        assert proof_file.steps[27].text == "\n      intros n."

        # Delete step in end of proof
        proof_file.delete_step(41)
        assert proof_file.steps[41].text == "\n    Admitted."

    def test_delete_and_add_outside_proof(self):
        # Add outside of proof
        len_steps = len(self.proof_file.steps)
        self.proof_file.add_step(1, "\nPrint plus.")
        assert len_steps + 1 == len(self.proof_file.steps)
        assert self.proof_file.steps[2].text == "\nPrint plus."

        # Delete outside of proof
        self.proof_file.delete_step(2)
        assert len_steps == len(self.proof_file.steps)
        assert self.proof_file.steps[2].text == "\n\nModule Out."

    def test_change_steps(self):
        proof_file = self.proof_file
        proof_file.change_steps(
            [
                CoqDeleteStep(6),
                CoqAddStep("\n      intros n.", 5),
                CoqAddStep("\n      Print minus.", 7),
            ]
        )

        test_proofs = get_test_proofs("tests/proof_file/expected/valid_file.yml")
        step = {
            "text": "\n      Print minus.",
            "goals": {
                "goals": {
                    "goals": [
                        {"hyps": [{"names": ["n"], "ty": "nat"}], "ty": "0 + n = n"}
                    ]
                },
                "position": {"line": 12, "character": 6},
            },
            "context": [
                {
                    "text": "Notation minus := Nat.sub (only parsing).",
                    "type": "NOTATION",
                }
            ],
        }
        add_step_defaults(step)
        test_proofs["proofs"][0]["steps"].insert(3, step)
        for step in test_proofs["proofs"][0]["steps"][4:]:
            step["goals"]["position"]["line"] += 1
        check_proof(test_proofs["proofs"][0], proof_file.proofs[0])

        # Add step in beginning of proof
        proof_file.change_steps([CoqAddStep("\n    Print plus.", 26)])
        assert proof_file.steps[27].text == "\n    Print plus."

        # Add step to end of proof
        proof_file.change_steps([CoqAddStep("\n    Print plus.", 31)])
        assert proof_file.steps[32].text == "\n    Print plus."

        # Delete step in beginning of proof
        proof_file.change_steps([CoqDeleteStep(27)])
        assert proof_file.steps[27].text == "\n      intros n."

        # Delete step in end of proof
        proof_file.change_steps([CoqDeleteStep(41)])
        assert proof_file.steps[41].text == "\n    Admitted."

    def test_change_steps_add_proof(self):
        proofs = len(self.proof_file.proofs)
        steps_taken = self.proof_file.steps_taken
        self.proof_file.change_steps(
            [
                CoqAddStep("\nTheorem change_steps : forall n:nat, 0 + n = n.", 1),
                CoqAddStep("\nProof.", 2),
                CoqAddStep("\nintros n.", 3),
                CoqAddStep("\nreduce_eq.", 4),
                CoqAddStep("\nQed.", 5),
            ]
        )
        assert self.proof_file.steps_taken == steps_taken + 5
        assert len(self.proof_file.proofs) == proofs + 1

    def test_change_steps_delete_proof(self):
        proofs = len(self.proof_file.proofs)
        steps_taken = self.proof_file.steps_taken
        self.proof_file.change_steps([CoqDeleteStep(14) for _ in range(7)])
        assert self.proof_file.steps_taken == steps_taken - 7
        assert len(self.proof_file.proofs) == proofs - 1

    def test_proof_changes(self):
        unproven = self.proof_file.unproven_proofs
        assert len(unproven) == 1
        assert (
            unproven[0].text
            == "Theorem mult_0_plus : ∀ n m : nat, S n * m = 0 + (S n * m)."
        )

        self.proof_file.change_proof(unproven[0], [ProofPop(), ProofAppend("\nQed.")])
        assert self.proof_file.unproven_proofs == []


class TestAddOpenProof(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_add_open_proof.v")

    def test_change_steps_add_open_proof(self):
        open_proofs = len(self.proof_file.open_proofs)
        proofs = len(self.proof_file.proofs)
        steps_taken = self.proof_file.steps_taken

        self.proof_file.change_steps(
            [
                CoqAddStep("\nTheorem change_steps : forall n:nat, 0 + n = n.", 0),
                CoqAddStep("\nProof.", 1),
                CoqAddStep("\nintros n.", 2),
            ]
        )
        assert self.proof_file.steps_taken == steps_taken + 3
        assert len(self.proof_file.proofs) == proofs
        assert len(self.proof_file.open_proofs) == open_proofs + 1

    def test_add_step_add_open_proofs(self):
        open_proofs = len(self.proof_file.open_proofs)
        self.proof_file.add_step(0, "\nTheorem add_step : forall n:nat, 0 + n = n.")
        self.proof_file.add_step(0, "\nTheorem add_step2 : forall n:nat, 0 + n = n.")
        self.proof_file.add_step(1, "\nTheorem add_step3 : forall n:nat, 0 + n = n.")
        assert len(self.proof_file.open_proofs) == open_proofs + 3
        assert (
            self.proof_file.open_proofs[0].text
            == "Theorem add_step2 : forall n:nat, 0 + n = n."
        )
        assert (
            self.proof_file.open_proofs[1].text
            == "Theorem add_step3 : forall n:nat, 0 + n = n."
        )
        assert (
            self.proof_file.open_proofs[2].text
            == "Theorem add_step : forall n:nat, 0 + n = n."
        )


class TestOpenClosedProof(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_delete_qed.v")

    def test_delete_qed(self):
        open_proofs = len(self.proof_file.open_proofs)
        proofs = len(self.proof_file.proofs)
        self.proof_file.delete_step(9)

        assert proofs - 1 == len(self.proof_file.proofs)
        assert open_proofs + 1 == len(self.proof_file.open_proofs)

        assert (
            self.proof_file.open_proofs[0].text
            == "Theorem delete_qed : forall n:nat, 0 + n = n."
        )
        assert (
            self.proof_file.open_proofs[1].text
            == "Theorem delete_qed2 : forall n:nat, 0 + n = n."
        )
        assert (
            self.proof_file.open_proofs[2].text
            == "Theorem delete_qed3 : forall n:nat, 0 + n = n."
        )

        assert (
            self.proof_file.proofs[0].text
            == "Theorem delete_qed4 : forall n:nat, 0 + n = n."
        )

    def test_close_qed(self):
        unproven = self.proof_file.unproven_proofs
        assert len(unproven) == 2
        for proof in unproven:
            self.proof_file.append_step(proof, "\nQed.")

        unproven = self.proof_file.unproven_proofs
        assert unproven == []


class TestProofSimpleFileChanges(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_simple_file.v")

    def test_end_of_file(self):
        steps = len(self.proof_file.steps)

        for _ in range(5):
            self.proof_file.add_step(self.proof_file.steps_taken - 1, "\nPrint plus.")
            assert len(self.proof_file.steps) == steps + 1
            self.proof_file.delete_step(self.proof_file.steps_taken)
            assert len(self.proof_file.steps) == steps

    def test_simple_file_changes(self):
        proof_file = self.proof_file
        proof_file.change_steps(
            [
                CoqDeleteStep(1),
                CoqDeleteStep(1),
                CoqDeleteStep(2),
                CoqDeleteStep(2),
                CoqDeleteStep(2),
                CoqAddStep("\nAdmitted.", 0),
                CoqAddStep("\nAdmitted.", 2),
            ]
        )
        # The last step is added in the end of the file
        proof_file.exec(1)

        assert len(proof_file.steps) == 4
        assert len(proof_file.proofs) == 2

        steps = [
            "Example test1: 1 + 1 = 2.",
            "\nAdmitted.",
            "\n\nExample test2: 1 + 1 + 1= 3.",
            "\nAdmitted.",
        ]
        for i, step in enumerate(steps):
            assert step == proof_file.steps[i].text

        assert proof_file.proofs[0].text == steps[0]
        assert proof_file.proofs[0].steps[0].text == steps[1]
        assert proof_file.proofs[1].text == steps[2].strip()
        assert proof_file.proofs[1].steps[0].text == steps[3]

    def test_simple_file_proof_change(self):
        proven = self.proof_file.proofs[-1]
        self.proof_file.pop_step(proven)
        self.proof_file.pop_step(proven)

        unproven = self.proof_file.unproven_proofs
        assert len(unproven) == 1
        self.proof_file.append_step(unproven[0], " reflexivity.")
        self.proof_file.append_step(unproven[0], " Qed.")

        unproven = self.proof_file.unproven_proofs
        assert unproven == []


class TestProofChangeWithNotation(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_change_with_notation.v")

    def test_change_with_notation(self):
        # Just checking if the program does not crash
        self.proof_file.add_step(len(self.proof_file.steps) - 3, " destruct (a <? n).")


class TestProofChangeInvalidFile(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_invalid_1.v")

    def test_change_invalid_file(self):
        with pytest.raises(InvalidFileException):
            self.proof_file.add_step(7, "Print plus.")
        with pytest.raises(InvalidFileException):
            self.proof_file.delete_step(7)
        with pytest.raises(InvalidFileException):
            self.proof_file.change_steps([])


class TestProofInvalidChanges(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_invalid_changes.v")
        self.n_steps = len(self.proof_file.steps)
        self.open_proofs = len(self.proof_file.open_proofs)
        self.closed_proofs = len(self.proof_file.proofs)
        self.open_steps = [len(proof.steps) for proof in self.proof_file.open_proofs]
        self.closed_steps = [len(proof.steps) for proof in self.proof_file.proofs]
        self.diagnostics = self.proof_file.diagnostics
        with open(self.proof_file.path, "r") as f:
            self.text = f.read()
        self.goals = []
        for proof in self.proof_file.proofs:
            for step in proof.steps:
                self.goals.append(step.goals)
        self.proof_file.run()

    def __check_rollback(self):
        assert self.n_steps == len(self.proof_file.steps)
        assert self.open_proofs == len(self.proof_file.open_proofs)
        assert self.closed_proofs == len(self.proof_file.proofs)
        for i in range(len(self.open_steps)):
            assert self.open_steps[i] == len(self.proof_file.open_proofs[i].steps)
        for i in range(len(self.closed_steps)):
            assert self.closed_steps[i] == len(self.proof_file.proofs[i].steps)
        assert self.proof_file.is_valid
        assert len(self.proof_file.diagnostics) == len(self.diagnostics)
        with open(self.proof_file.path, "r") as f:
            assert self.text == f.read()
        i = 0
        for proof in self.proof_file.proofs:
            for step in proof.steps:
                assert repr(step.goals) == repr(self.goals[i])
                i += 1

    def test_invalid_add(self):
        # File becomes invalid
        with pytest.raises(InvalidAddException):
            # Add a non-existing tactic
            self.proof_file.add_step(6, "\n    invalid_tactic.")
        self.__check_rollback()
        with pytest.raises(InvalidAddException):
            # Add an existing tactic that fails
            self.proof_file.add_step(6, "\n    inversion 1.")
        self.__check_rollback()
        with pytest.raises(InvalidAddException):
            # Add a tactic when there are no goals
            self.proof_file.add_step(7, "\n    reflexivity.")
        self.__check_rollback()
        with pytest.raises(InvalidAddException):
            # Add a tactic with undefined tokens
            self.proof_file.add_step(6, "\n    invalid_tactic x $$$ y.")
        self.__check_rollback()

        # File remains valid but not a valid step
        with pytest.raises(InvalidAddException):
            # Add two valid steps
            self.proof_file.add_step(6, "\n    Check A.x. Check A.x.")
        self.__check_rollback()
        with pytest.raises(InvalidAddException):
            # Modify the previous step
            self.proof_file.add_step(6, "x.")
        self.__check_rollback()
        with pytest.raises(InvalidAddException):
            # Modify the next step
            self.proof_file.add_step(6, " try")
        self.__check_rollback()
        # TODO: Handle this case. Should this be allowed or not?
        # with pytest.raises(InvalidAddException):
        #     # Modify existing steps and add a new one
        #     self.proof_file.add_step(6, "x. Check A.x. try")
        #     self.__check_rollback()
        with pytest.raises(InvalidAddException):
            # Add whitespaces to end of file
            self.proof_file.add_step(8, "\n \t")
        self.__check_rollback()
        with pytest.raises(InvalidAddException):
            # Add comment to end of file
            self.proof_file.add_step(8, "\n(* I'm useless *)")
        self.__check_rollback()

    def test_invalid_delete(self):
        with pytest.raises(InvalidDeleteException):
            # Delete proof term
            self.proof_file.delete_step(4)
        self.__check_rollback()
        with pytest.raises(InvalidDeleteException):
            # Delete necessary proof step
            self.proof_file.delete_step(7)
        self.__check_rollback()

    def test_invalid_changes(self):
        with pytest.raises(InvalidChangeException):
            # Delete proof body
            self.proof_file.change_steps([CoqDeleteStep(6) for _ in range(2)])
        self.__check_rollback()


class TestProofChangeEmptyProof(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_change_empty.v")

    def test_change_empty_proof(self):
        proof_file = self.proof_file
        assert len(proof_file.proofs) == 0
        assert len(proof_file.open_proofs) == 1
        assert len(proof_file.open_proofs[0].steps) == 1
        assert proof_file.open_proofs[0].steps[0].text == "\nProof."
        lemma_end = proof_file.open_proofs[0].step.ast.range.end
        texts = [" Check\nplus.", "\nreflexivity.", " Print\nplus.", " Admitted."]

        # Add [Admitted.]
        proof_file.add_step(1, texts[3])
        # Step was added to the end of the file
        proof_file.exec(1)
        assert len(proof_file.proofs) == 1
        steps = proof_file.proofs[0].steps
        assert len(steps) == 2
        assert steps[1].text == texts[3]
        assert len(proof_file.open_proofs) == 0
        admitted_start = steps[1].ast.range.start
        admitted_start = Position(admitted_start.line, admitted_start.character)

        # Add [reflexivity.]
        proof_file.add_step(1, texts[1])
        assert len(proof_file.proofs) == 1
        steps = proof_file.proofs[0].steps
        assert len(steps) == 3
        assert steps[1].text == texts[1]
        assert len(proof_file.open_proofs) == 0
        refl_end = steps[1].ast.range.end
        refl_end = Position(refl_end.line, refl_end.character)
        # [Admitted.] AST changes
        assert steps[2].ast.range.start.line == admitted_start.line + 1
        assert steps[2].ast.range.start.character == refl_end.character + 1

        # Add [Print plus.] and [Check plus.]
        proof_file.change_steps([CoqAddStep(texts[2], 2), CoqAddStep(texts[0], 1)])
        assert len(proof_file.proofs) == 1
        steps = proof_file.proofs[0].steps
        assert len(steps) == 5
        assert steps[1].text == texts[0]
        assert steps[3].text == texts[2]
        assert len(proof_file.open_proofs) == 0
        print_end = steps[3].ast.range.end
        print_end = Position(print_end.line, print_end.character)
        check_end = steps[1].ast.range.end
        check_end = Position(check_end.line, check_end.character)
        # [reflexivity.] AST changes
        assert steps[2].ast.range.end.line == refl_end.line + 1
        # [Admitted.] AST changes
        assert steps[4].ast.range.start.line == admitted_start.line + 3
        assert steps[4].ast.range.start.character == print_end.character + 1

        # Delete [Proof.] and [Admitted.]
        proof_file.change_steps([CoqDeleteStep(1), CoqDeleteStep(4)])
        assert len(proof_file.proofs) == 0
        assert len(proof_file.open_proofs) == 1
        steps = proof_file.open_proofs[0].steps
        assert len(steps) == 3
        # [Check plus.] AST changes
        assert steps[0].ast.range.end.line == check_end.line - 1
        assert steps[0].ast.range.start.character == lemma_end.character + 1
        # [reflexivity.] AST changes
        assert steps[1].ast.range.end.line == refl_end.line
        # [Print plus.] AST changes
        assert steps[2].ast.range.end.line == print_end.line - 1
        assert steps[2].ast.range.start.character == refl_end.character + 1

        # Delete [reflexivity.]
        proof_file.delete_step(2)
        # Delete [Check plus.]
        proof_file.delete_step(1)
        assert len(proof_file.proofs) == 0
        assert len(proof_file.open_proofs) == 1
        steps = proof_file.open_proofs[0].steps
        assert len(steps) == 1
        # [Print plus.] AST changes
        assert steps[0].ast.range.end.line == print_end.line - 3
        assert steps[0].ast.range.start.character == lemma_end.character + 1

        # Delete Lemma statement
        proof_file.delete_step(0)
        assert len(proof_file.proofs) == 0
        assert len(proof_file.open_proofs) == 0


class TestProofChangeNestedProofs(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_nested_proofs.v")

    def test_change_nested_proofs(self):
        proof_file = self.proof_file

        # Close proofs in file
        proof_file.add_step(proof_file.steps_taken - 1, "\nQed.")
        proof_file.add_step(proof_file.steps_taken, "\nQed.")
        assert len(proof_file.proofs) == 2
        assert len(proof_file.open_proofs) == 2

        # Close proofs in ProofFile
        proof_file.exec(2)
        assert len(proof_file.proofs) == 4
        assert len(proof_file.open_proofs) == 0

        # Re-open proofs in ProofFile
        proof_file.exec(-2)
        assert len(proof_file.proofs) == 2
        assert len(proof_file.open_proofs) == 2

        # Close proofs in ProofFile again to check rollback
        proof_file.exec(2)
        assert len(proof_file.proofs) == 4
        assert len(proof_file.open_proofs) == 0

        # Re-open proofs in file
        proof_file.exec(-2)
        proof_file.delete_step(proof_file.steps_taken + 1)
        proof_file.delete_step(proof_file.steps_taken)

        assert len(proof_file.proofs) == 2
        assert len(proof_file.open_proofs) == 2
        assert proof_file.steps_taken == len(proof_file.steps)


class TestProofChangeObligation(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_obligation.v")

    def test_change_obligation(self):
        proof_file = self.proof_file

        # Delete unwanted steps
        proof_file.change_steps([CoqDeleteStep(2) for _ in range(30)])
        proof_file.change_steps([CoqDeleteStep(16), CoqDeleteStep(2)])
        proof_file.change_steps([CoqDeleteStep(12) for _ in range(3)])

        # Add a Program definition in the middle of a proof
        program = (
            "\nProgram Definition idx (n : nat) : { x : nat | x = n } :="
            + "\n  if dec (Nat.leb n 0) then 0%nat"
            + "\n  else pred (S n)."
        )
        proof_file.add_step(9, program)

        # Add a proof for each obligation of the new Program
        proof = ["\nNext Obligation.", "\n  dummy_tactic n e.", "\nQed."]
        for i, step in enumerate(proof):
            proof_file.add_step(12 + i, step)
        for i, step in enumerate(proof):
            proof_file.add_step(15 + i, step)

        texts = [
            "Obligation 1 of id with reflexivity.",
            "Obligation 1 of id : type.",
            "Next Obligation.",
            "Next Obligation.",
        ]
        programs = [
            ("#[program]", "id", "pred (S n)"),
            ("Program", "id", "S (pred n)"),
            ("Program", "id", "S (pred n)"),
            ("Program", "idx", "pred (S n)"),
        ]

        # Steps were added to the end of the file
        proof_file.run()

        # Check the proofs
        assert len(proof_file.proofs) == 4
        assert len(proof_file.open_proofs) == 0
        for i, proof in enumerate(proof_file.proofs):
            assert proof.text == texts[i]
            assert proof.program is not None
            assert (
                proof.program.text
                == programs[i][0]
                + " Definition "
                + programs[i][1]
                + " (n : nat) : { x : nat | x = n } := if dec (Nat.leb n 0) then 0%nat else "
                + programs[i][2]
                + "."
            )
            assert len(proof.steps) == 2
            assert proof.steps[0].text == "\n  dummy_tactic n e."

        # Delete new Program and last Next Obligation proof
        for i in range(3):
            proof_file.delete_step(proof_file.steps_taken - 1)
        proof_file.delete_step(10)

        # Check the proofs
        assert len(proof_file.proofs) == 3
        assert len(proof_file.open_proofs) == 0
        for i, proof in enumerate(proof_file.proofs):
            assert proof.text == texts[i]
            assert proof.program is not None
            assert (
                proof.program.text
                == programs[i][0]
                + " Definition "
                + programs[i][1]
                + " (n : nat) : { x : nat | x = n } := if dec (Nat.leb n 0) then 0%nat else "
                + programs[i][2]
                + "."
            )
            assert len(proof.steps) == 2
            assert proof.steps[0].text == "\n  dummy_tactic n e."


class TestProofChangeGoals(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_change_goals.v")

    def test_change_goals(self):
        proof_file = self.proof_file

        # Step back to see result of [\ninduction n.]
        proof_file.exec(-1)
        # [\ninduction n.] maintains open goals
        assert len(proof_file.current_goals.goals.goals) > 0

        # Replace [\ninduction n.] with equally sized step
        proof_file.change_steps(
            [
                CoqAddStep("\nreflexivity.", 1),
                CoqDeleteStep(3),
            ]
        )

        # [\nreflexivity.] leaves no open goals
        # Must check if the goals were properly updated
        assert len(proof_file.current_goals.goals.goals) == 0
