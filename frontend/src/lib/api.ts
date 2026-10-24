export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public retryable: boolean,
    public requestId?: string,
    public status?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(
      'Could not reach the service. Retry or continue writing.',
      'network_error',
      true,
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      data?.error?.message || `Request failed (${response.status}).`,
      data?.error?.code || 'service_error',
      Boolean(data?.error?.retryable),
      data?.request_id,
      response.status,
    );
  if (data === null)
    throw new ApiError('The service returned an invalid response.', 'invalid_response', true);
  return data as T;
}
export function post<T>(path: string, body: unknown, signal?: AbortSignal) {
  return api<T>(path, { method: 'POST', body: JSON.stringify(body), signal });
}
export const uid = () => crypto.randomUUID();
export const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'The operation failed. Retry.';
