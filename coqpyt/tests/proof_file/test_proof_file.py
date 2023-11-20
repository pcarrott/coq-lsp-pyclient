import os
import shutil
import uuid
import subprocess
import pytest
import tempfile

from coqpyt.coq.lsp.structs import *
from coqpyt.coq.exceptions import *
from coqpyt.coq.changes import *
from coqpyt.coq.structs import TermType
from coqpyt.coq.proof_file import ProofFile

from utility import *

versionId: VersionedTextDocumentIdentifier = None
proof_file: ProofFile = None
workspace: str = None
file_path: str = ""


@pytest.fixture
def setup(request):
    global proof_file, versionId, workspace, file_path
    file_path, workspace = request.param[0], request.param[1]
    if len(request.param) == 3 and request.param[2]:
        new_path = os.path.join(
            tempfile.gettempdir(), "test" + str(uuid.uuid4()).replace("-", "") + ".v"
        )
        shutil.copyfile(os.path.join("tests/resources", file_path), new_path)
        file_path = new_path
    else:
        file_path = os.path.join("tests/resources", file_path)
    if workspace is not None:
        workspace = os.path.join(os.getcwd(), "tests/resources", workspace)
        subprocess.run(f"cd {workspace} && make", shell=True, capture_output=True)
    uri = "file://" + file_path
    proof_file = ProofFile(file_path, timeout=60, workspace=workspace)
    proof_file.run()
    versionId = VersionedTextDocumentIdentifier(uri, 1)
    yield


@pytest.fixture
def teardown(request):
    yield
    if workspace is not None:
        subprocess.run(f"cd {workspace} && make clean", shell=True, capture_output=True)
    proof_file.close()
    if (
        hasattr(request, "param")
        and len(request.param) == 1
        and request.param[0]
        and os.path.exists(file_path)
    ):
        os.remove(file_path)


class TestProofValidFile(SetupProofFile):
    def setup_method(self, method):
        self.setup("test_valid.v")

    def teardown_method(self, method):
        self.teardown()

    def test_valid_file(self):
        proofs = self.proof_file.proofs
        check_proofs("tests/proof_file/valid_file.yml", proofs)


@pytest.mark.parametrize("setup", [("test_valid.v", None)], indirect=True)
def test_valid_file(setup, teardown):
    proofs = proof_file.proofs
    check_proofs("tests/proof_file/valid_file.yml", proofs)


@pytest.mark.parametrize("setup", [("test_valid.v", None, True)], indirect=True)
@pytest.mark.parametrize("teardown", [(True,)], indirect=True)
def test_delete_and_add(setup, teardown):
    proof_file.delete_step(6)

    test_proofs = get_test_proofs(
        "tests/proof_file/valid_file.yml", 2
    )
    test_proofs["proofs"][0]["steps"].pop(1)
    test_proofs["proofs"][0]["steps"][0]["goals"]["version"] = 1
    for i, step in enumerate(test_proofs["proofs"][0]["steps"]):
        if i != 0:
            step["goals"]["position"]["line"] -= 1
        if i != len(test_proofs["proofs"][0]["steps"]) - 1:
            step["goals"]["goals"]["goals"][0]["hyps"] = []
            step["goals"]["goals"]["goals"][0]["ty"] = "∀ n : nat, 0 + n = n"
    check_proof(test_proofs["proofs"][0], proof_file.proofs[0])

    proof_file.add_step(5, "\n      intros n.")

    test_proofs = get_test_proofs(
        "tests/proof_file/valid_file.yml", 3
    )
    test_proofs["proofs"][0]["steps"][0]["goals"]["version"] = 1
    check_proof(test_proofs["proofs"][0], proof_file.proofs[0])

    # Check if context is changed correctly
    proof_file.add_step(7, "\n      Print minus.")
    step = {
        "text": "\n      Print minus.",
        "goals": {
            "goals": {
                "goals": [{"hyps": [{"names": ["n"], "ty": "nat"}], "ty": "0 + n = n"}]
            },
            "position": {"line": 12, "character": 6},
        },
        "context": [
            {"text": "Notation minus := Nat.sub (only parsing).", "type": "NOTATION"}
        ],
    }
    add_step_defaults(step, 4)
    test_proofs["proofs"][0]["steps"].insert(3, step)
    for i, step in enumerate(test_proofs["proofs"][0]["steps"][4:]):
        step["goals"]["version"] = 4
        step["goals"]["position"]["line"] += 1
    check_proof(test_proofs["proofs"][0], proof_file.proofs[0])

    # Add outside of proof
    with pytest.raises(NotImplementedError):
        proof_file.add_step(25, "\n    Print plus.")

    # Add step in beginning of proof
    proof_file.add_step(26, "\n    Print plus.")
    assert proof_file.steps[27].text == "\n    Print plus."

    # Delete outside of proof
    with pytest.raises(NotImplementedError):
        proof_file.delete_step(33)

    # Add step to end of proof
    proof_file.add_step(31, "\n    Print plus.")
    assert proof_file.steps[32].text == "\n    Print plus."

    # Delete step in beginning of proof
    proof_file.delete_step(27)
    assert proof_file.steps[27].text == "\n      intros n."

    # Delete step in end of proof
    proof_file.delete_step(41)
    assert proof_file.steps[41].text == "\n    Admitted."


@pytest.mark.parametrize("setup", [("test_valid.v", None, True)], indirect=True)
@pytest.mark.parametrize("teardown", [(True,)], indirect=True)
def test_proof_change_steps(setup, teardown):
    proof_file.change_steps(
        [
            CoqDeleteStep(6),
            CoqAddStep("\n      intros n.", 5),
            CoqAddStep("\n      Print minus.", 7),
        ]
    )

    test_proofs = get_test_proofs(
        "tests/proof_file/valid_file.yml", 4
    )
    test_proofs["proofs"][0]["steps"][0]["goals"]["version"] = 1
    step = {
        "text": "\n      Print minus.",
        "goals": {
            "goals": {
                "goals": [{"hyps": [{"names": ["n"], "ty": "nat"}], "ty": "0 + n = n"}]
            },
            "position": {"line": 12, "character": 6},
        },
        "context": [
            {"text": "Notation minus := Nat.sub (only parsing).", "type": "NOTATION"}
        ],
    }
    add_step_defaults(step, 4)
    test_proofs["proofs"][0]["steps"].insert(3, step)
    for step in test_proofs["proofs"][0]["steps"][4:]:
        step["goals"]["position"]["line"] += 1
    check_proof(test_proofs["proofs"][0], proof_file.proofs[0])

    # Add outside of proof
    with pytest.raises(NotImplementedError):
        proof_file.change_steps([CoqAddStep("\n    Print plus.", 25)])

    # Add step in beginning of proof
    proof_file.change_steps([CoqAddStep("\n    Print plus.", 26)])
    assert proof_file.steps[27].text == "\n    Print plus."

    # # Delete outside of proof
    with pytest.raises(NotImplementedError):
        proof_file.change_steps([CoqDeleteStep(33)])

    # # Add step to end of proof
    proof_file.change_steps([CoqAddStep("\n    Print plus.", 31)])
    assert proof_file.steps[32].text == "\n    Print plus."

    # # Delete step in beginning of proof
    proof_file.change_steps([CoqDeleteStep(27)])
    assert proof_file.steps[27].text == "\n      intros n."

    # # Delete step in end of proof
    proof_file.change_steps([CoqDeleteStep(41)])
    assert proof_file.steps[41].text == "\n    Admitted."


@pytest.mark.parametrize("setup", [("test_valid.v", None, True)], indirect=True)
@pytest.mark.parametrize("teardown", [(True,)], indirect=True)
def test_invalid_change(setup, teardown):
    n_old_steps = len(proof_file.steps)
    old_diagnostics = proof_file.diagnostics
    old_goals = []
    for proof in proof_file.proofs:
        for step in proof.steps:
            old_goals.append(step.goals)

    def check_rollback():
        with open(proof_file.path, "r") as f:
            assert n_old_steps == len(proof_file.steps)
            assert old_diagnostics == proof_file.diagnostics
            assert proof_file.is_valid
            assert "invalid_tactic" not in f.read()
            i = 0
            for proof in proof_file.proofs:
                for step in proof.steps:
                    assert step.goals == old_goals[i]
                    i += 1

    with pytest.raises(InvalidDeleteException):
        proof_file.delete_step(9)
        check_rollback()
    with pytest.raises(InvalidDeleteException):
        proof_file.delete_step(16)
        check_rollback()
    with pytest.raises(InvalidStepException):
        proof_file.add_step(7, "invalid_tactic")
        check_rollback()
    with pytest.raises(InvalidStepException):
        proof_file.add_step(7, "invalid_tactic.")
        check_rollback()
    with pytest.raises(InvalidStepException):
        proof_file.add_step(7, "\n    invalid_tactic.")
        check_rollback()
    with pytest.raises(InvalidStepException):
        proof_file.add_step(7, "\n    invalid_tactic x $$$ y.")
        check_rollback()


@pytest.mark.parametrize("setup", [("test_bug.v", None, True)], indirect=True)
@pytest.mark.parametrize("teardown", [(True,)], indirect=True)
def test_change_notation(setup, teardown):
    # Just checking if the program does not crash
    proof_file.add_step(len(proof_file.steps) - 3, " destruct (a <? n).")


@pytest.mark.parametrize("setup", [("test_invalid_1.v", None, True)], indirect=True)
@pytest.mark.parametrize("teardown", [(True,)], indirect=True)
def test_change_invalid(setup, teardown):
    with pytest.raises(InvalidFileException):
        proof_file.add_step(7, "Print plus.")


@pytest.mark.parametrize("setup", [("test_change_empty.v", None, True)], indirect=True)
@pytest.mark.parametrize("teardown", [(True,)], indirect=True)
def test_change_empty(setup, teardown):
    assert len(proof_file.proofs) == 0
    assert len(proof_file.open_proofs) == 1

    proof_file.add_step(len(proof_file.steps) - 2, "\nAdmitted.")
    assert proof_file.steps[-2].text == "\nAdmitted."
    assert len(proof_file.open_proofs[0].steps) == 2
    assert proof_file.open_proofs[0].steps[-1].text == "\nAdmitted."

    proof_file.delete_step(len(proof_file.steps) - 2)
    assert len(proof_file.steps) == 3
    assert len(proof_file.open_proofs[0].steps) == 1


@pytest.mark.parametrize(
    "setup", [("test_imports/test_import.v", "test_imports/")], indirect=True
)
def test_imports(setup, teardown):
    check_proofs("tests/proof_file/imports.yml", proof_file.proofs)


@pytest.mark.parametrize("setup", [("test_non_ending_proof.v", None)], indirect=True)
def test_non_ending_proof(setup, teardown):
    assert len(proof_file.open_proofs) == 1
    assert len(proof_file.open_proofs[0].steps) == 3


@pytest.mark.parametrize("setup", [("test_exists_notation.v", None)], indirect=True)
def test_exists_notation(setup, teardown):
    """Checks if the exists notation is handled. The exists notation is defined
    with 'exists', but the search can be done without the '.
    """
    assert (
        proof_file.context.get_notation("exists _ .. _ , _", "type_scope").text
        == "Notation \"'exists' x .. y , p\" := (ex (fun x => .. (ex (fun y => p)) ..)) (at level 200, x binder, right associativity, format \"'[' 'exists' '/ ' x .. y , '/ ' p ']'\") : type_scope."
    )


@pytest.mark.parametrize("setup", [("test_list_notation.v", None)], indirect=True)
def test_list_notation(setup, teardown):
    check_proofs("tests/proof_file/list_notation.yml", proof_file.proofs)


@pytest.mark.parametrize("setup", [("test_unknown_notation.v", None)], indirect=True)
def test_unknown_notation(setup, teardown):
    """Checks if it is able to handle the notation { _ } that is unknown for the
    Locate command because it is a default notation.
    """
    with pytest.raises(NotationNotFoundException):
        assert proof_file.context.get_notation("{ _ }", "")


@pytest.mark.parametrize("setup", [("test_nested_proofs.v", None, True)], indirect=True)
def test_nested_proofs(setup, teardown):
    proofs = proof_file.proofs
    assert len(proofs) == 2

    steps = ["\n    intros n.", "\n    simpl; reflexivity.", "\n    Qed."]
    assert len(proofs[0].steps) == len(steps)
    for i, step in enumerate(proofs[0].steps):
        assert step.text == steps[i]

    theorem = "Theorem mult_0_plus : forall n m : nat, S n * m = 0 + (S n * m)."
    steps = [
        "\nProof.",
        "\nintros n m.",
        "\n\nrewrite <- (plus_O_n ((S n) * m)).",
        "\nreflexivity.",
        "\nQed.",
    ]
    assert proofs[1].text == theorem
    assert len(proofs[1].steps) == len(steps)
    for i, step in enumerate(proofs[1].steps):
        assert step.text == steps[i]

    proofs = proof_file.open_proofs
    assert len(proofs) == 2

    steps = [
        "\n    intros n.",
        "\n    simpl; reflexivity.",
    ]
    assert len(proofs[0].steps) == 2
    for i, step in enumerate(proofs[0].steps):
        assert step.text == steps[i]

    steps = [
        "\n    intros n.",
        "\n    simpl; reflexivity.",
    ]
    assert len(proofs[1].steps) == 2
    for i, step in enumerate(proofs[1].steps):
        assert step.text == steps[i]

    # Close proofs
    proof_file.exec(-1)
    proof_file.add_step(proof_file.steps_taken - 1, "\nQed.")
    proof_file.add_step(proof_file.steps_taken - 1, "\nQed.")
    proof_file.exec(2)
    assert len(proof_file.proofs) == 4
    assert len(proof_file.open_proofs) == 0

    # Re-open proofs
    proof_file.exec(-2)
    assert len(proof_file.proofs) == 2
    assert len(proof_file.open_proofs) == 2

    # Attempt to leave proof
    with pytest.raises(NotImplementedError):
        proof_file.exec(-3)

    # Check rollback
    assert len(proof_file.proofs) == 2
    assert len(proof_file.open_proofs) == 2
    proof_file.exec(2)
    assert len(proof_file.proofs) == 4
    assert len(proof_file.open_proofs) == 0


@pytest.mark.parametrize("setup", [("test_theorem_tokens.v", None)], indirect=True)
def test_theorem_tokens(setup, teardown):
    proofs = proof_file.proofs
    assert len(proofs) == 7
    assert proofs[0].type == TermType.REMARK
    assert proofs[1].type == TermType.FACT
    assert proofs[2].type == TermType.COROLLARY
    assert proofs[3].type == TermType.PROPOSITION
    assert proofs[4].type == TermType.PROPERTY
    assert proofs[5].type == TermType.THEOREM
    assert proofs[6].type == TermType.LEMMA


@pytest.mark.parametrize("setup", [("test_bullets.v", None)], indirect=True)
def test_bullets(setup, teardown):
    proofs = proof_file.proofs
    assert len(proofs) == 1
    steps = [
        "\nProof.",
        "\n    intros x y.",
        " split.",
        "\n    -",
        "reflexivity.",
        "\n    -",
        " reflexivity.",
        "\nQed.",
    ]
    assert len(proofs[0].steps) == len(steps)
    for i, step in enumerate(proofs[0].steps):
        assert step.text == steps[i]


@pytest.mark.parametrize("setup", [("test_obligation.v", None)], indirect=True)
def test_obligation(setup, teardown):
    proofs = proof_file.proofs
    assert len(proofs) == 11

    statement_context = [
        ("Inductive nat : Set := | O : nat | S : nat -> nat.", TermType.INDUCTIVE, []),
        ("Notation dec := sumbool_of_bool.", TermType.NOTATION, []),
        ("Notation leb := Nat.leb (only parsing).", TermType.NOTATION, []),
        ("Notation pred := Nat.pred (only parsing).", TermType.NOTATION, []),
        (
            'Notation "{ x : A | P }" := (sig (A:=A) (fun x => P)) : type_scope.',
            TermType.NOTATION,
            [],
        ),
        ('Notation "x = y" := (eq x y) : type_scope.', TermType.NOTATION, []),
    ]
    texts = [
        "Obligation 2 of id1.",
        "Next Obligation of id1.",
        "Obligation 2 of id2 : type with reflexivity.",
        "Next Obligation of id2 with reflexivity.",
        "Next Obligation.",
        "Next Obligation with reflexivity.",
        "Obligation 1.",
        "Obligation 2 : type with reflexivity.",
        "Obligation 1 of id with reflexivity.",
        "Obligation 1 of id : type.",
        "Obligation 2 : type.",
    ]
    programs = [
        ("id1", "S (pred n)"),
        ("id1", "S (pred n)"),
        ("id2", "S (pred n)"),
        ("id2", "S (pred n)"),
        ("id3", "S (pred n)"),
        ("id3", "S (pred n)"),
        ("id4", "S (pred n)"),
        ("id4", "S (pred n)"),
        ("id", "pred (S n)"),
        ("id", "S (pred n)"),
        ("id", "S (pred n)"),
    ]

    for i, proof in enumerate(proofs):
        compare_context(statement_context, proof.context)
        assert proof.text == texts[i]
        assert proof.program is not None
        assert (
            proof.program.text
            == "Program Definition "
            + programs[i][0]
            + " (n : nat) : { x : nat | x = n } := if dec (leb n 0) then 0%nat else "
            + programs[i][1]
            + "."
        )
        assert len(proof.steps) == 2
        assert proof.steps[0].text == "\n  dummy_tactic n e."


@pytest.mark.parametrize("setup", [("test_module_type.v", None)], indirect=True)
def test_module_type(setup, teardown):
    # We ignore proofs inside a Module Type since they can't be used outside
    # and should be overriden.
    assert len(proof_file.proofs) == 1


@pytest.mark.parametrize("setup", [("test_type_class.v", None)], indirect=True)
def test_type_class(setup, teardown):
    assert len(proof_file.proofs) == 2
    assert len(proof_file.proofs[0].steps) == 4
    assert (
        proof_file.proofs[0].text
        == "#[refine] Global Instance unit_EqDec : TypeClass.EqDecNew unit := { eqb_new x y := true }."
    )

    context = [
        (
            "Class EqDecNew (A : Type) := { eqb_new : A -> A -> bool ; eqb_leibniz_new : forall x y, eqb_new x y = true -> x = y ; eqb_ident_new : forall x, eqb_new x x = true }.",
            TermType.CLASS,
            ["TypeClass"],
        ),
        ("Inductive unit : Set := tt : unit.", TermType.INDUCTIVE, []),
        (
            "Inductive bool : Set := | true : bool | false : bool.",
            TermType.INDUCTIVE,
            [],
        ),
    ]
    compare_context(context, proof_file.proofs[0].context)

    assert (
        proof_file.proofs[1].text
        == "Instance test : TypeClass.EqDecNew unit -> TypeClass.EqDecNew unit."
    )

    context = [
        (
            'Notation "A -> B" := (forall (_ : A), B) : type_scope.',
            TermType.NOTATION,
            [],
        ),
        (
            "Class EqDecNew (A : Type) := { eqb_new : A -> A -> bool ; eqb_leibniz_new : forall x y, eqb_new x y = true -> x = y ; eqb_ident_new : forall x, eqb_new x x = true }.",
            TermType.CLASS,
            ["TypeClass"],
        ),
        ("Inductive unit : Set := tt : unit.", TermType.INDUCTIVE, []),
    ]
    compare_context(context, proof_file.proofs[1].context)


@pytest.mark.parametrize("setup", [("test_goal.v", None)], indirect=True)
def test_goal(setup, teardown):
    assert len(proof_file.proofs) == 3
    goals = [
        "Definition ignored : forall P Q: Prop, (P -> Q) -> P -> Q.",
        "Goal forall P Q: Prop, (P -> Q) -> P -> Q.",
        "Goal forall P Q: Prop, (P -> Q) -> P -> Q.",
    ]
    for i, proof in enumerate(proof_file.proofs):
        assert proof.text == goals[i]
        compare_context(
            [
                (
                    'Notation "A -> B" := (forall (_ : A), B) : type_scope.',
                    TermType.NOTATION,
                    [],
                )
            ],
            proof.context,
        )


@pytest.mark.parametrize("setup", [("test_simple_file.v", None, True)], indirect=True)
@pytest.mark.parametrize("teardown", [(True,)], indirect=True)
def test_simple_file_changes(setup, teardown):
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
    assert len(proof_file.steps) == 5
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


@pytest.mark.parametrize("setup", [("test_proof_cmd.v", None)], indirect=True)
def test_proof_cmd(setup, teardown):
    assert len(proof_file.proofs) == 3
    goals = [
        "Goal ∃ (m : nat), S m = n.",
        "Goal ∃ (m : nat), S m = n.",
        "Goal nat.",
    ]
    proofs = [
        "\n  Proof using Hn.",
        "\n  Proof with auto.",
        "\n  Proof 0.",
    ]
    for i, proof in enumerate(proof_file.proofs):
        assert proof.text == goals[i]
        assert proof.steps[0].text == proofs[i]


@pytest.mark.parametrize("setup", [("test_section_terms.v", None)], indirect=True)
def test_section_terms(setup, teardown):
    assert len(proof_file.proofs) == 1
    assert proof_file.proofs[0].text == "Let ignored : nat."
    assert len(proof_file.context.local_terms) == 0
