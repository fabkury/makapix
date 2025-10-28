export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

const publicBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost/api";

export async function requestJson<TResponse>(
  path: string,
  options: RequestInit = {},
  method: HttpMethod = "GET",
): Promise<TResponse> {
  const url = `${publicBaseUrl}${path}`;
  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed (${response.status}): ${body}`);
  }

  return response.json() as Promise<TResponse>;
}

export async function postJson<TResponse>(
  path: string,
  payload: unknown,
): Promise<TResponse> {
  return requestJson<TResponse>(path, { body: JSON.stringify(payload) }, "POST");
}
