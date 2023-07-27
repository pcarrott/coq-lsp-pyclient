import time
import subprocess
from pylspclient.json_rpc_endpoint import JsonRpcEndpoint
from pylspclient.lsp_endpoint import LspEndpoint
from pylspclient.lsp_client import LspClient
from pylspclient import lsp_structs
from coqlspclient import coq_lsp_structs
from typing import Dict


class CoqLspClient(LspClient):
    __DEFAULT_INIT_OPTIONS = {
        "max_errors": 120000000,
        "show_coq_info_messages": True,
        "eager_diagnostics": False,
    }

    def __init__(
        self,
        root_uri: str,
        timeout: int = 2,
        memory_limit: int = 2097152,
        init_options: Dict = __DEFAULT_INIT_OPTIONS,
    ):
        proc = subprocess.Popen(
            f"ulimit -v {memory_limit}; coq-lsp",
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            shell=True,
        )
        json_rpc_endpoint = JsonRpcEndpoint(proc.stdin, proc.stdout)
        lsp_endpoint = LspEndpoint(json_rpc_endpoint, timeout=timeout)
        super().__init__(lsp_endpoint)
        workspaces = [{"name": "coq-lsp", "uri": root_uri}]
        self.initialize(
            proc.pid,
            "",
            root_uri,
            init_options,
            {},
            "off",
            workspaces,
        )
        self.initialized()

    def __wait_for_operation(self):
        timeout = self.lsp_endpoint.timeout
        while not self.lsp_endpoint.completed_operation and timeout > 0:
            if self.lsp_endpoint.shutdown_flag:
                raise lsp_structs.ResponseError(
                    lsp_structs.ErrorCodes.ServerQuit, "Server quit"
                )
            time.sleep(0.1)
            timeout -= 0.1

        if timeout <= 0:
            self.shutdown()
            self.exit()
            raise lsp_structs.ResponseError(
                lsp_structs.ErrorCodes.ServerQuit, "Server quit"
            )

    def didOpen(self, textDocument: lsp_structs.TextDocumentItem):
        super().didOpen(textDocument)
        self.__wait_for_operation()

    def didChange(
        self,
        textDocument: lsp_structs.VersionedTextDocumentIdentifier,
        contentChanges: list[lsp_structs.TextDocumentContentChangeEvent],
    ):
        super().didChange(textDocument, contentChanges)
        self.__wait_for_operation()

    def proof_goals(self, textDocument, position):
        result_dict = self.lsp_endpoint.call_method(
            "proof/goals", textDocument=textDocument, position=position
        )
        result_dict["textDocument"] = lsp_structs.VersionedTextDocumentIdentifier(
            **result_dict["textDocument"]
        )
        result_dict["position"] = lsp_structs.Position(
            result_dict["position"]["line"], result_dict["position"]["character"]
        )

        if result_dict["goals"] is not None:
            result_dict["goals"] = coq_lsp_structs.GoalConfig.parse(
                result_dict["goals"]
            )

        for i, message in enumerate(result_dict["messages"]):
            if not isinstance(message, str):
                if message["range"]:
                    message["range"] = lsp_structs.Range(**message["range"])
                result_dict["messages"][i] = coq_lsp_structs.Message(**message)

        return coq_lsp_structs.GoalAnswer(**result_dict)

    def get_queries(self, textDocument, keyword):
        """
        keyword might be Search, Print, Check, etc...
        """
        uri = textDocument.uri
        if textDocument.uri.startswith("file://"):
            uri = uri[7:]

        with open(uri, "r") as doc:
            if textDocument.uri not in self.lsp_endpoint.diagnostics:
                return []
            lines = doc.readlines()
            diagnostics = self.lsp_endpoint.diagnostics[textDocument.uri]
            searches = {}

            for diagnostic in diagnostics:
                command = lines[
                    diagnostic.range["start"]["line"] : diagnostic.range["end"]["line"]
                    + 1
                ]
                if len(command) == 1:
                    command[0] = command[0][
                        diagnostic.range["start"]["character"] : diagnostic.range[
                            "end"
                        ]["character"]
                        + 1
                    ]
                else:
                    command[0] = command[0][diagnostic.range["start"]["character"] :]
                    command[-1] = command[-1][
                        : diagnostic.range["end"]["character"] + 1
                    ]
                command = "".join(command).strip()

                if command.startswith(keyword):
                    query = command[len(keyword) + 1 : -1]
                    if query not in searches:
                        searches[query] = []
                    searches[query].append(
                        coq_lsp_structs.Result(diagnostic.range, diagnostic.message)
                    )

            res = []
            for query, results in searches.items():
                res.append(coq_lsp_structs.Query(query, results))

        return res

    def has_error(self, textDocument):
        uri = textDocument.uri
        if textDocument.uri.startswith("file://"):
            uri = uri[7:]

        if textDocument.uri not in self.lsp_endpoint.diagnostics:
            return False

        diagnostics = self.lsp_endpoint.diagnostics[textDocument.uri]
        for diagnostic in diagnostics:
            if diagnostic.severity == 1:
                return True
        return False

    def get_document(self, textDocument):
        result_dict = self.lsp_endpoint.call_method(
            "coq/getDocument", textDocument=textDocument
        )
        return result_dict

    def save_vo(self, textDocument):
        """
        The uri in the textDocument should contain an absolute path.
        """
        result_dict = self.lsp_endpoint.call_method(
            "coq/saveVo", textDocument=textDocument
        )
        return result_dict
