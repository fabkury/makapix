import Head from "next/head";
import type { GetServerSideProps, InferGetServerSidePropsType } from "next";

type Props = {
  status: string;
  checkedAt: string;
};

export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const internalBase =
    process.env.API_INTERNAL_URL ?? "http://api:8000";

  try {
    const response = await fetch(`${internalBase}/health`);
    if (!response.ok) {
      throw new Error(`API health check failed: ${response.status}`);
    }
    const data = await response.json();

    return {
      props: {
        status: data.status ?? "unknown",
        checkedAt: new Date().toISOString(),
      },
    };
  } catch (error) {
    console.error("Failed to check API health:", error);
    return {
      props: {
        status: "error",
        checkedAt: new Date().toISOString(),
      },
    };
  }
};

const HomePage = ({
  status,
  checkedAt,
}: InferGetServerSidePropsType<typeof getServerSideProps>) => {
  return (
    <>
      <Head>
        <title>Makapix Dev Portal</title>
      </Head>
      <main className="container">
        <h1>Makapix Dev Environment</h1>
        <section>
          <h2>API Health</h2>
          <p>
            Status: <strong>{status}</strong>
          </p>
          <p>
            Checked at: <code>{checkedAt}</code>
          </p>
        </section>
        <section>
          <h2>What&apos;s next?</h2>
          <ul>
            <li>
              Explore the <a href="/demo">MQTT demo page</a>.
            </li>
            <li>
              Update code locally and watch hot reload through Docker Compose.
            </li>
            <li>
              Run <code>make api.test</code> or <code>make fmt</code> to keep things tidy.
            </li>
          </ul>
        </section>
      </main>
      <style jsx>{`
        .container {
          max-width: 720px;
          margin: 4rem auto;
          padding: 0 1rem;
          font-family: system-ui, sans-serif;
        }
        h1 {
          font-size: 2.5rem;
          margin-bottom: 1rem;
        }
        h2 {
          margin-top: 2rem;
        }
        ul {
          padding-left: 1.25rem;
        }
        code {
          background: #f4f4f5;
          padding: 0.15rem 0.35rem;
          border-radius: 4px;
        }
      `}</style>
    </>
  );
};

export default HomePage;
