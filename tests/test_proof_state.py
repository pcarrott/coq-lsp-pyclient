import os
import pytest
from pylspclient.lsp_structs import *
from coqlspclient.coq_lsp_structs import *
from coqlspclient.proof_state import ProofState

versionId: VersionedTextDocumentIdentifier = None
state: ProofState = None


@pytest.fixture
def setup(request):
    global state, versionId
    file_path = os.path.join("tests/resources", request.param)
    uri = "file://" + file_path
    state = ProofState(file_path, timeout=60)
    versionId = VersionedTextDocumentIdentifier(uri, 1)
    yield


@pytest.fixture
def teardown():
    yield
    state.close()


@pytest.mark.parametrize("setup", ["test_proof_steps.v"], indirect=True)
def test_proof_steps(setup, teardown):
    proof_steps = state.proof_steps()
    assert len(proof_steps) == 4

    texts = [
        "\n      intros n.",
        "\n      Print plus.",
        "\n      Print Nat.add.",
        "\n      reduce_eq.",
        "\n    Qed.",
    ]
    goals = [
        GoalAnswer(
            versionId,
            Position(7, 10),
            [],
            GoalConfig([Goal([], "∀ n : nat, 0 + n = n")], [], [], [], None),
        ),
        GoalAnswer(
            versionId,
            Position(8, 15),
            [],
            GoalConfig(
                [Goal([Hyp(["n"], "nat", None)], "0 + n = n")], [], [], [], None
            ),
        ),
        GoalAnswer(
            versionId,
            Position(9, 17),
            [],
            GoalConfig(
                [Goal([Hyp(["n"], "nat", None)], "0 + n = n")], [], [], [], None
            ),
        ),
        GoalAnswer(
            versionId,
            Position(10, 20),
            [],
            GoalConfig(
                [Goal([Hyp(["n"], "nat", None)], "0 + n = n")], [], [], [], None
            ),
        ),
        GoalAnswer(versionId, Position(11, 16), [], GoalConfig([], [], [], [], None)),
    ]
    contexts = [
        [],
        ["Notation plus := Nat.add (only parsing)."],
        [
            'Fixpoint add n m := match n with | 0 => m | S p => S (p + m) end where "n + m" := (add n m) : nat_scope.'
        ],
        ["Ltac reduce_eq := simpl; reflexivity."],
        None,
    ]

    for i in range(5):
        assert proof_steps[0][i].text == texts[i]
        assert str(proof_steps[0][i].goals) == str(goals[i])
        assert proof_steps[0][i].context == contexts[i]

    texts = [
        "\n    intros n m.",
        "\n    rewrite -> (plus_O_n (S n * m)).",
        "\n    Compute True /\\ True.",
        "\n    reflexivity.",
        "\n  Qed.",
    ]
    goals = [
        GoalAnswer(
            versionId,
            Position(19, 8),
            [],
            GoalConfig(
                [Goal([], "∀ n m : nat, 0 + S n * m = S n * m")], [], [], [], None
            ),
        ),
        GoalAnswer(
            versionId,
            Position(20, 15),
            [],
            GoalConfig(
                [Goal([Hyp(["n", "m"], "nat", None)], "0 + S n * m = S n * m")],
                [],
                [],
                [],
                None,
            ),
        ),
        GoalAnswer(
            versionId,
            Position(21, 36),
            [],
            GoalConfig(
                [Goal([Hyp(["n", "m"], "nat", None)], "S n * m = S n * m")],
                [],
                [],
                [],
                None,
            ),
        ),
        GoalAnswer(
            versionId,
            Position(22, 25),
            [],
            GoalConfig(
                [Goal([Hyp(["n", "m"], "nat", None)], "S n * m = S n * m")],
                [],
                [],
                [],
                None,
            ),
        ),
        GoalAnswer(versionId, Position(23, 16), [], GoalConfig([], [], [], [], None)),
    ]
    contexts = [
        [],
        [
            "Lemma plus_O_n : forall n:nat, 0 + n = n.",
            'Notation "x * y" := (Nat.mul x y) : nat_scope',
            "Inductive nat : Set := | O : nat | S : nat -> nat.",
        ],
        [
            'Notation "A /\\ B" := (and A B) : type_scope',
            "Inductive True : Prop := I : True.",
        ],
        [],
        None,
    ]

    for i in range(5):
        assert proof_steps[1][i].text == texts[i]
        assert str(proof_steps[1][i].goals) == str(goals[i])
        assert proof_steps[1][i].context == contexts[i]

    texts = [
        "\n      intros n.",
        "\n      Compute mk_example n n.",
        "\n      Compute Out.In.plus_O_n.",
        "\n      reduce_eq.",
        "\n    Qed.",
    ]
    goals = [
        GoalAnswer(
            versionId,
            Position(32, 10),
            [],
            GoalConfig([Goal([], "∀ n : nat, n = 0 + n")], [], [], [], None),
        ),
        GoalAnswer(
            versionId,
            Position(33, 15),
            [],
            GoalConfig(
                [Goal([Hyp(["n"], "nat", None)], "n = 0 + n")], [], [], [], None
            ),
        ),
        GoalAnswer(
            versionId,
            Position(34, 29),
            [],
            GoalConfig(
                [Goal([Hyp(["n"], "nat", None)], "n = 0 + n")], [], [], [], None
            ),
        ),
        GoalAnswer(
            versionId,
            Position(35, 30),
            [],
            GoalConfig(
                [Goal([Hyp(["n"], "nat", None)], "n = 0 + n")], [], [], [], None
            ),
        ),
        GoalAnswer(versionId, Position(36, 16), [], GoalConfig([], [], [], [], None)),
    ]
    contexts = [
        [],
        ["Record example := mk_example { fst : nat; snd : nat }."],
        ["Theorem plus_O_n : forall n:nat, 0 + n = n."],
        ["Ltac reduce_eq := simpl; reflexivity."],
        None,
    ]

    for i in range(5):
        assert proof_steps[2][i].text == texts[i]
        assert str(proof_steps[2][i].goals) == str(goals[i])
        assert proof_steps[2][i].context == contexts[i]

    texts = [
        "\n      intros n m.",
        "\n      rewrite <- (Fst.plus_O_n (|n| * m)).",
        "\n      Compute {| Fst.fst := n; Fst.snd := n |}.",
        "\n      reflexivity.",
        "\n    Qed.",
    ]
    goals = [
        GoalAnswer(
            versionId,
            Position(45, 10),
            [],
            GoalConfig(
                [Goal([], "∀ n m : nat, | n | * m = 0 + | n | * m")], [], [], [], None
            ),
        ),
        GoalAnswer(
            versionId,
            Position(46, 17),
            [],
            GoalConfig(
                [Goal([Hyp(["n", "m"], "nat", None)], "| n | * m = 0 + | n | * m")],
                [],
                [],
                [],
                None,
            ),
        ),
        GoalAnswer(
            versionId,
            Position(47, 42),
            [],
            GoalConfig(
                [Goal([Hyp(["n", "m"], "nat", None)], "| n | * m = | n | * m")],
                [],
                [],
                [],
                None,
            ),
        ),
        GoalAnswer(
            versionId,
            Position(48, 47),
            [],
            GoalConfig(
                [Goal([Hyp(["n", "m"], "nat", None)], "| n | * m = | n | * m")],
                [],
                [],
                [],
                None,
            ),
        ),
        GoalAnswer(versionId, Position(49, 18), [], GoalConfig([], [], [], [], None)),
    ]
    contexts = [
        [],
        [
            "Theorem plus_O_n : forall n:nat, n = 0 + n.",
            'Notation "x * y" := (Nat.mul x y) : nat_scope',
            'Notation "| a |" := (S a)',
        ],
        ["Record example := mk_example { fst : nat; snd : nat }."],
        [],
        None,
    ]

    for i in range(5):
        assert proof_steps[3][i].text == texts[i]
        assert str(proof_steps[3][i].goals) == str(goals[i])
        assert proof_steps[3][i].context == contexts[i]


@pytest.mark.parametrize("setup", ["test_proof_steps.v"], indirect=True)
def test_is_valid(setup, teardown):
    found_error = state.is_invalid()
    assert found_error == False


@pytest.mark.parametrize("setup", ["test_is_invalid_1.v"], indirect=True)
def test_is_invalid_1(setup, teardown):
    found_error = state.is_invalid()
    assert found_error == True


@pytest.mark.parametrize("setup", ["test_is_invalid_2.v"], indirect=True)
def test_is_invalid_2(setup, teardown):
    found_error = state.is_invalid()
    assert found_error == True
