import { api, getStoredAccessToken, refreshAccessToken } from "@/store/api";

/*
The two read endpoints are ordinary RTK Query endpoints. `sendChatMessage` is
not, and cannot be: /rag/chat answers with text/event-stream, and
fetchBaseQuery reads a response to completion before handing it over. Going
through it would work but would surrender the streaming — the answer would
appear all at once after ~15s instead of the first token after ~2s.

So that one endpoint uses queryFn with a manual fetch, which means it also has
to do by hand the two things fetchBaseQuery was doing for free: attaching the
access token, and refreshing it on a 401.
*/

const API_BASE_URL = "/api";

// each server-sent event is "data: {json}\n\n"
const SSE_DATA_PREFIX = "data: ";
const SSE_FRAME_SEPARATOR = "\n\n";

/**
 * Yield each decoded event from an SSE response body.
 *
 * Network chunks do not line up with event boundaries — one read can carry
 * half an event, or three of them — so completed frames are cut off the front
 * of a buffer and whatever is left waits for the next read.
 */
async function* readServerSentEvents(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();

        if (done) {
            break;
        }

        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf(SSE_FRAME_SEPARATOR);

        while (boundary !== -1) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + SSE_FRAME_SEPARATOR.length);

            const line = frame
                .split("\n")
                .find((candidate) => candidate.startsWith(SSE_DATA_PREFIX));

            if (line) {
                yield JSON.parse(line.slice(SSE_DATA_PREFIX.length));
            }

            boundary = buffer.indexOf(SSE_FRAME_SEPARATOR);
        }
    }
}

/** POST the question, returning the raw streaming response. */
const postChat = (body, signal) =>
    fetch(`${API_BASE_URL}/rag/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            Authorization: `Bearer ${getStoredAccessToken()}`,
        },
        body: JSON.stringify(body),
        signal,
    });

/**
 * Read one answer out of the stream.
 *
 * The backend reports failures two different ways, because a stream cannot
 * change a status line it has already sent: anything it catches before the
 * response starts is a normal HTTP status, anything after is an `error` event
 * partway through the body. Both end up as an RTK Query error here.
 */
async function consumeChatStream(response, onDelta) {
    let conversationId = null;
    let answer = "";

    for await (const event of readServerSentEvents(response)) {
        if (event.type === "conversation") {
            // sent before any text, so a caller that started without an id can
            // attach the reply to a conversation immediately
            conversationId = event.conversation_id;
            continue;
        }

        if (event.type === "delta") {
            answer += event.text;
            onDelta?.(event.text, answer);
            continue;
        }

        if (event.type === "error") {
            return {
                error: {
                    status: "STREAM_ERROR",
                    code: event.code,
                    data: { detail: event.message },
                    // whatever arrived before it failed; for `not_persisted`
                    // this is a complete answer that simply was not saved
                    conversationId,
                    answer,
                },
            };
        }
    }

    return { data: { conversationId, answer } };
}

export const ragApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getConversations: builder.query({
            query: ({ skip = 0, limit = 20 } = {}) =>
                `/rag/conversations?skip=${skip}&limit=${limit}`,
            providesTags: ["Conversation"],
        }),

        getConversationMessages: builder.query({
            query: (conversationId) =>
                `/rag/conversations/${conversationId}/messages`,
            providesTags: (_result, _error, conversationId) => [
                { type: "ConversationMessage", id: conversationId },
            ],
        }),

        /**
         * Retitle a conversation.
         *
         * Patched into the cached list before the request resolves, the way
         * `updateIssue` does it. Without that the row shows the OLD title for
         * the moment between leaving the edit box and the refetch landing,
         * which reads as the rename having failed.
         */
        renameConversation: builder.mutation({
            query: ({ conversationId, title }) => ({
                url: `/rag/conversations/${conversationId}`,
                method: "PATCH",
                body: { title },
            }),

            async onQueryStarted(
                { conversationId, title, queryArgs = { skip: 0, limit: 20 } },
                { dispatch, queryFulfilled },
            ) {
                const patch = dispatch(
                    api.util.updateQueryData("getConversations", queryArgs, (draft) => {
                        const conversation = draft.find((item) => item.id === conversationId);
                        if (conversation) {
                            conversation.title = title;
                        }
                    }),
                );

                try {
                    await queryFulfilled;
                } catch {
                    patch.undo();
                }
            },

            invalidatesTags: ["Conversation"],
        }),

        /**
         * Delete a conversation. Its messages cascade on the server.
         *
         * Removed from the cached list immediately for the same reason as
         * above, and the transcript tag is invalidated so a deleted
         * conversation's messages are never served from cache.
         */
        deleteConversation: builder.mutation({
            query: (conversationId) => ({
                url: `/rag/conversations/${conversationId}`,
                method: "DELETE",
            }),

            async onQueryStarted(conversationId, { dispatch, queryFulfilled }) {
                const patch = dispatch(
                    api.util.updateQueryData(
                        "getConversations",
                        { skip: 0, limit: 20 },
                        (draft) => {
                            // spliced rather than filtered: the recipe then
                            // only mutates, instead of relying on Immer's
                            // return-a-new-value rule
                            const index = draft.findIndex(
                                (item) => item.id === conversationId,
                            );
                            if (index !== -1) {
                                draft.splice(index, 1);
                            }
                        },
                    ),
                );

                try {
                    await queryFulfilled;
                } catch {
                    patch.undo();
                }
            },

            invalidatesTags: (_result, _error, conversationId) => [
                "Conversation",
                { type: "ConversationMessage", id: conversationId },
            ],
        }),

        /**
         * Ask a question and stream the answer.
         *
         * Resolves with the whole answer once the stream closes. Pass
         * `onDelta` to render tokens as they arrive — it is called with
         * (chunk, textSoFar).
         *
         * `conversationId` is omitted on the first turn; the backend creates
         * one and returns its id as the first event.
         */
        sendChatMessage: builder.mutation({
            queryFn: async ({ question, conversationId, onDelta }, { dispatch, signal }) => {
                const body = { question };

                if (conversationId) {
                    body.conversation_id = conversationId;
                }

                try {
                    let response = await postChat(body, signal);

                    // fetchBaseQuery would have done this; a manual fetch has
                    // to, or a chat would be the one call that fails on an
                    // expired token while everything else quietly refreshes
                    if (response.status === 401 && (await refreshAccessToken(dispatch))) {
                        response = await postChat(body, signal);
                    }

                    if (!response.ok) {
                        return {
                            error: {
                                status: response.status,
                                data: await response.json().catch(() => null),
                            },
                        };
                    }

                    return await consumeChatStream(response, onDelta);
                } catch (error) {
                    return {
                        error: { status: "FETCH_ERROR", error: String(error) },
                    };
                }
            },

            // a first turn creates a conversation, and every turn moves one up
            // the recently-active ordering, so the list is stale either way
            invalidatesTags: (result) => [
                "Conversation",
                ...(result?.conversationId
                    ? [{ type: "ConversationMessage", id: result.conversationId }]
                    : []),
            ],
        }),
    }),
});

export const {
    useGetConversationsQuery,
    useGetConversationMessagesQuery,
    useRenameConversationMutation,
    useDeleteConversationMutation,
    useSendChatMessageMutation,
} = ragApi;
