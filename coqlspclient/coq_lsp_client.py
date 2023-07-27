import time
import subprocess
from pylspclient.json_rpc_endpoint import JsonRpcEndpoint
from pylspclient.lsp_endpoint import LspEndpoint
from pylspclient.lsp_client import LspClient
from pylspclient.lsp_structs import *
from coqlspclient.coq_lsp_structs import *
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
        """Abstraction to interact with coq-lsp

        Args:
            root_uri (str): URI to the workspace where coq-lsp will run
                The URI can be either a file or a folder.
            timeout (int, optional): Timeout used for the coq-lsp operations.
                Defaults to 2.
            memory_limit (int, optional): RAM limit for the coq-lsp process
                in kbytes. Defaults to 2097152.
            init_options (Dict, optional): Initialization options for coq-lsp server.
                Relevant options are:
                    max_errors (int): Maximum number of errors per file, after that,
                        coq-lsp will stop checking the file. Defaults to 120000000.
                    eager_diagnostics (bool): Send diagnostics as document is processed.
                        If false, diagnostics are only send when Coq finishes
                        processing the whole file. Defaults to false.
                    show_coq_info_messages (bool): Show Coq's info messages as diagnostics.
                        Defaults to false.
                    show_notices_as_diagnostics (bool): Show Coq's notice messages
                        as diagnostics, such as `About` and `Search` operations.
                        Defaults to false.
                    debug (bool): Enable Debug in Coq Server. Defaults to false.
                    pp_type (int): Method to print Coq Terms.
                        0 = Print to string
                        1 = Use jsCoq's Pp rich layout printer
                        2 = Coq Layout Engine
                        Defaults to 1.
        """
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
                raise ResponseError(ErrorCodes.ServerQuit, "Server quit")
            time.sleep(0.1)
            timeout -= 0.1

        if timeout <= 0:
            self.shutdown()
            self.exit()
            raise ResponseError(ErrorCodes.ServerQuit, "Server quit")

    def didOpen(self, textDocument: TextDocumentItem):
        """Open a text document in the server.

        Args:
            textDocument (TextDocumentItem): Text document to open
        """
        super().didOpen(textDocument)
        self.__wait_for_operation()

    def didChange(
        self,
        textDocument: VersionedTextDocumentIdentifier,
        contentChanges: list[TextDocumentContentChangeEvent],
    ):
        """Submit changes on a text document already open on the server.

        Args:
            textDocument (VersionedTextDocumentIdentifier): Text document changed.
            contentChanges (list[TextDocumentContentChangeEvent]): Changes made.
        """
        super().didChange(textDocument, contentChanges)
        self.__wait_for_operation()

    def proof_goals(
        self, textDocument: TextDocumentIdentifier, position: Position
    ) -> Optional[GoalAnswer]:
        """Get proof goals and relevant information at a position.

        Args:
            textDocument (TextDocumentIdentifier): Text document to consider.
            position (Position): Position used to get the proof goals.

        Returns:
            GoalAnswer: Contains the goals at a position, messages associated
                to the position and if errors exist, the top error at the position.
        """
        result_dict = self.lsp_endpoint.call_method(
            "proof/goals", textDocument=textDocument, position=position
        )
        result_dict["textDocument"] = VersionedTextDocumentIdentifier(
            **result_dict["textDocument"]
        )
        result_dict["position"] = Position(
            result_dict["position"]["line"], result_dict["position"]["character"]
        )

        if result_dict["goals"] is not None:
            result_dict["goals"] = GoalConfig.parse(result_dict["goals"])

        for i, message in enumerate(result_dict["messages"]):
            if not isinstance(message, str):
                if message["range"]:
                    message["range"] = Range(**message["range"])
                result_dict["messages"][i] = Message(**message)

        return GoalAnswer(**result_dict)

    def get_document(
        self, textDocument: TextDocumentIdentifier
    ) -> Optional[FlecheDocument]:
        """Get the AST of a text document.

        Args:
            textDocument (TextDocumentIdentifier): Text document

        Returns:
            Optional[FlecheDocument]: Serialized version of Fleche's document
        """
        result_dict = self.lsp_endpoint.call_method(
            "coq/getDocument", textDocument=textDocument
        )
        return FlecheDocument.parse(result_dict)

    def save_vo(self, textDocument: TextDocumentIdentifier):
        """Save a compiled file to disk.

        Args:
            textDocument (TextDocumentIdentifier): File to be saved.
                The uri in the textDocument should contain an absolute path.
        """
        self.lsp_endpoint.call_method("coq/saveVo", textDocument=textDocument)

    # TODO: handle performance data notification and file checking progress
