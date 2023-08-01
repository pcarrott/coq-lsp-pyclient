import os
import shutil
import uuid
import tempfile
from pylspclient.lsp_structs import (
    TextDocumentItem,
    VersionedTextDocumentIdentifier,
    TextDocumentContentChangeEvent,
    ResponseError,
    ErrorCodes,
)
from coqlspclient.coq_lsp_structs import ProofStep
from coqlspclient.coq_lsp_structs import (
    CoqError,
    CoqErrorCodes,
    Result,
    Query,
    FileContext,
)
from coqlspclient.coq_file import CoqFile
from coqlspclient.coq_lsp_client import CoqLspClient
from typing import List, Optional


class _AuxFile(object):
    def __init__(self, file_path: Optional[str] = None, timeout: int = 2):
        self.__init_path(file_path)
        uri = f"file://{self.path}"
        self.coq_lsp_client = CoqLspClient(uri, timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __init_path(self, file_path):
        temp_dir = tempfile.gettempdir()
        new_path = os.path.join(
            temp_dir, "aux_" + str(uuid.uuid4()).replace("-", "") + ".v"
        )
        with open(new_path, "w"):
            # Create empty file
            pass

        if file_path is not None:
            shutil.copyfile(file_path, new_path)

        self.path = new_path
        self.version = 1

    def read(self):
        with open(self.path, "r") as f:
            return f.read()

    def write(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def append(self, text):
        with open(self.path, "a") as f:
            f.write(text)

    def __handle_exception(self, e):
        if not (isinstance(e, ResponseError) and e.code == ErrorCodes.ServerQuit.value):
            self.coq_lsp_client.shutdown()
            self.coq_lsp_client.exit()
        os.remove(self.path)

    def didOpen(self):
        uri = f"file://{self.path}"
        try:
            self.coq_lsp_client.didOpen(TextDocumentItem(uri, "coq", 1, self.read()))
        except Exception as e:
            self.__handle_exception(e)
            raise e

    def didChange(self):
        uri = f"file://{self.path}"
        self.version += 1
        try:
            self.coq_lsp_client.didChange(
                VersionedTextDocumentIdentifier(uri, self.version),
                [TextDocumentContentChangeEvent(None, None, self.read())],
            )
        except Exception as e:
            self.__handle_exception(e)
            raise e

    def __get_queries(self, keyword):
        uri = f"file://{self.path}"
        if uri not in self.coq_lsp_client.lsp_endpoint.diagnostics:
            return []

        searches = {}
        lines = self.read().split("\n")
        for diagnostic in self.coq_lsp_client.lsp_endpoint.diagnostics[uri]:
            command = lines[
                diagnostic.range["start"]["line"] : diagnostic.range["end"]["line"] + 1
            ]
            if len(command) == 1:
                command[0] = command[0][
                    diagnostic.range["start"]["character"] : diagnostic.range["end"][
                        "character"
                    ]
                    + 1
                ]
            else:
                command[0] = command[0][diagnostic.range["start"]["character"] :]
                command[-1] = command[-1][: diagnostic.range["end"]["character"] + 1]
            command = "".join(command).strip()

            if command.startswith(keyword):
                query = command[len(keyword) + 1 : -1]
                if query not in searches:
                    searches[query] = []
                searches[query].append(Result(diagnostic.range, diagnostic.message))

        res = []
        for query, results in searches.items():
            res.append(Query(query, results))

        return res

    def get_diagnostics(self, keyword, search, line):
        for query in self.__get_queries(keyword):
            if query.query == f"{search}":
                for result in query.results:
                    if result.range["start"]["line"] == line:
                        return result.message
                break
        return None

    def close(self):
        self.coq_lsp_client.shutdown()
        self.coq_lsp_client.exit()
        os.remove(self.path)

    @staticmethod
    def get_context(file_path: str, timeout: int):
        with _AuxFile(file_path=file_path, timeout=timeout) as aux_file:
            aux_file.append("\nPrint Libraries.")
            aux_file.didOpen()

            last_line = len(aux_file.read().split("\n")) - 1
            libraries = aux_file.get_diagnostics("Print Libraries", "", last_line)
            libraries = list(map(lambda line: line.strip(), libraries.split("\n")[1:-1]))
            for library in libraries:
                aux_file.append(f"\nLocate Library {library}.")
            aux_file.didChange()

            context = FileContext()
            for i, library in enumerate(libraries):
                v_file = aux_file.get_diagnostics(
                    "Locate Library", library, last_line + i + 1
                ).split("\n")[-1][:-1]
                coq_file = CoqFile(v_file, library=library, timeout=timeout)
                coq_file.run()

                # FIXME: we ignore the usage of Local from imported files to
                # simplify the implementation. However, they can be used:
                # https://coq.inria.fr/refman/language/core/modules.html?highlight=local#coq:attr.local
                for term in list(coq_file.context.terms.keys()):
                    if coq_file.context.terms[term].startswith("Local"):
                        coq_file.context.terms.pop(term)

                context.update(**vars(coq_file.context))
                coq_file.close()

        return context


class ProofState(object):
    """Allows to get information about the proofs of a Coq file

    Attributes:
        coq_file (CoqFile): Coq file to interact with
    """

    def __init__(self, coq_file: CoqFile):
        """Creates a ProofState

        Args:
            coq_file (CoqFile): Coq file to interact with

        Raises:
            CoqError: If the provided file is not valid.
        """
        self.coq_file = coq_file
        if not self.coq_file.is_valid:
            self.coq_file.close()
            raise CoqError(
                CoqErrorCodes.InvalidFile,
                f"At least one error found in file {coq_file.path}",
            )
        self.coq_file.context = _AuxFile.get_context(coq_file.path, coq_file.timeout)
        self.__aux_file = _AuxFile(timeout=coq_file.timeout)
        self.__current_step = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __get_term(self, name):
        for i in range(len(self.coq_file.curr_module), -1, -1):
            curr_name = ".".join(self.coq_file.curr_module[:i] + [name])
            if curr_name in self.coq_file.context.terms:
                return self.coq_file.context.terms[curr_name]
        return None

    def __locate(self, search, line):
        nots = self.__aux_file.get_diagnostics("Locate", f'"{search}"', line).split(
            "\n"
        )
        fun = lambda x: x.endswith("(default interpretation)")
        if len(nots) > 1:
            return list(filter(fun, nots))[0][:-25]
        else:
            return nots[0][:-25] if fun(nots[0]) else nots[0]

    def __step_context(self):
        def traverse_ast(el):
            if isinstance(el, dict):
                return [x for v in el.values() for x in traverse_ast(v)]
            elif isinstance(el, list) and len(el) == 3 and el[0] == "Ser_Qualid":
                id = ".".join([l[1] for l in el[1][1][::-1]] + [el[2][1]])
                term = self.__get_term(id)
                return [] if term is None else [(lambda x: x, term)]
            elif isinstance(el, list) and len(el) == 4 and el[0] == "CNotation":
                line = len(self.__aux_file.read().split("\n"))
                self.__aux_file.append(f'\nLocate "{el[2][1]}".')
                return [(self.__locate, el[2][1], line)] + traverse_ast(el[1:])
            elif isinstance(el, list):
                return [x for v in el for x in traverse_ast(v)]

            return []

        return traverse_ast(self.__current_step.ast.span)

    def __step(self):
        self.__current_step = self.coq_file.exec()[0]
        self.__aux_file.append(self.__current_step.text)

    def __get_steps(self):
        def trim_step_text():
            range = self.__current_step.ast.range
            nlines = range.end.line - range.start.line
            text = self.__current_step.text.split("\n")[-nlines:]
            text[0] = text[0][range.start.character :]
            return "\n".join(text)

        steps = []
        while self.coq_file.in_proof:
            try:
                goals = self.coq_file.current_goals()
            except Exception as e:
                self.__aux_file.close()
                raise e

            self.__step()
            text = trim_step_text()
            context_calls = self.__step_context()
            steps.append((text, goals, context_calls))
        return steps

    def get_proofs(self) -> List[List[ProofStep]]:
        """Gets all the proofs in the file and their corresponding steps.

        Returns:
            List[ProofStep]: Each element has the list of steps for a single
                proof of the Coq file. The proofs are ordered by the order
                they are written on the file. The steps include the context
                used for each step and the goals in that step.
        """

        def get_proof_step(step):
            context, calls = [], [call[0](*call[1:]) for call in step[2]]
            [context.append(call) for call in calls if call not in context]
            return ProofStep(step[0], step[1], context)

        proofs = []
        while not self.coq_file.checked:
            self.__step()
            if self.coq_file.in_proof:
                proofs.append(self.__get_steps())

        try:
            self.__aux_file.didOpen()
        except Exception as e:
            self.coq_file.close()
            raise e

        return [list(map(get_proof_step, steps)) for steps in proofs]

    def close(self):
        """Closes all resources used by this object."""
        self.coq_file.close()
        self.__aux_file.close()
