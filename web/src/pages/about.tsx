import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';

type TabValue = 'about' | 'rules' | 'moderation';

const validTabs: TabValue[] = ['about', 'rules', 'moderation'];

export default function AboutPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabValue>('about');

  // Handle URL query param for deep linking
  useEffect(() => {
    const tabParam = router.query.tab as string;
    if (tabParam && validTabs.includes(tabParam as TabValue)) {
      setActiveTab(tabParam as TabValue);
    }
  }, [router.query.tab]);

  const handleTabChange = (value: string) => {
    setActiveTab(value as TabValue);
    // Update URL without triggering navigation
    const url = value === 'about' ? '/about' : `/about?tab=${value}`;
    router.replace(url, undefined, { shallow: true });
  };

  return (
    <Layout title="About" description="About Makapix Club - Community rules, reputation system, and moderation policies">
      <div className="about-container">
        <Tabs value={activeTab} onValueChange={handleTabChange} className="tabs-root">
          <TabsList className="tabs-list">
            <TabsTrigger value="about" className="tab-trigger">About</TabsTrigger>
            <TabsTrigger value="rules" className="tab-trigger">Rules</TabsTrigger>
            <TabsTrigger value="moderation" className="tab-trigger">Moderation</TabsTrigger>
          </TabsList>

          <TabsContent value="about" className="tab-content">
            <AboutTab />
          </TabsContent>

          <TabsContent value="rules" className="tab-content">
            <RulesTab />
          </TabsContent>

          <TabsContent value="moderation" className="tab-content">
            <ModerationTab />
          </TabsContent>
        </Tabs>
      </div>

      <style jsx>{`
        .about-container {
          max-width: 720px;
          margin: 0 auto;
          padding: 32px 24px 64px;
        }

        .about-container :global(.tabs-root) {
          width: 100%;
        }

        .about-container :global(.tabs-list) {
          display: flex;
          gap: 8px;
          width: 100%;
          height: auto;
          padding: 8px;
          margin-bottom: 32px;
          justify-content: center;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 12px;
        }

        .about-container :global(.tab-trigger) {
          flex: 1;
          max-width: 160px;
          padding: 10px 20px;
          font-size: 0.95rem;
          color: rgba(255, 255, 255, 0.7);
        }

        .about-container :global(.tab-trigger:hover) {
          color: rgba(255, 255, 255, 0.9);
        }

        .about-container :global(.tab-trigger[data-state='active']) {
          color: var(--accent-cyan);
        }

        .about-container :global(.tab-content) {
          margin-top: 0;
        }

        @media (max-width: 480px) {
          .about-container {
            padding: 24px 16px 48px;
          }

          .about-container :global(.tabs-list) {
            gap: 6px;
            padding: 6px;
          }

          .about-container :global(.tab-trigger) {
            padding: 8px 12px;
            font-size: 0.9rem;
          }
        }
      `}</style>
    </Layout>
  );
}

function AboutTab() {
  return (
    <article className="tab-article">
      <h1>Welcome to Makapix Club</h1>
      
      <p className="lead">
        Makapix Club (MPX) is a lightweight social network for pixel artists and DIY makers.
        We bring together creators who love pixel art and the makers who bring that art into
        the physical world.
      </p>

      <h2>Who is MPX for?</h2>
      
      <p>
        <strong>Artists</strong> can post their pixel art, receive feedback, and connect with
        a community of fellow creators. Track how your work performs with detailed private
        statistics that go far beyond simple view counts.
      </p>
      
      <p>
        <strong>DIY Makers</strong> can discover pixel art to display on LED matrices, pixel
        screens, and other physical devices. Our comprehensive API enables automated downloads
        and real-time notifications when your favorite artists post new work.
      </p>
      
      <p>
        <strong>Everyone</strong> is welcome to browse, enjoy, and react to the amazing pixel
        art shared by our community.
      </p>

      <h2>What makes MPX different?</h2>
      
      <p>
        <strong>Real-world displays.</strong> We are the only open community that delivers
        pixel art directly to physical displays—LED matrices, pixel screens, and other devices
        beyond your phone, tablet, or computer.
      </p>
      
      <p>
        <strong>Maker API.</strong> Our comprehensive API supports automated interactions with
        the server. Download artworks programmatically and receive real-time updates via MQTT
        when new content is posted.
      </p>
      
      <p>
        <strong>Artist statistics.</strong> We provide best-in-class private analytics that
        help you understand how your art reaches and engages the community—much more than
        just likes and view counts.
      </p>

      <h2>Founded</h2>
      
      <p>
        Makapix Club was founded in November 2025 by{' '}
        <span className="user-mention">@Fab</span> and{' '}
        <span className="user-mention">@m o n s t e r</span>.
      </p>

      <h2>Open Source</h2>
      
      <p>
        Makapix Club is open source. You can find our code on{' '}
        <a href="https://github.com/fabkury/makapix" target="_blank" rel="noopener noreferrer">
          GitHub
        </a>.
      </p>

      <style jsx>{`
        .tab-article {
          color: var(--text-secondary);
          line-height: 1.7;
        }

        .tab-article h1 {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 24px 0;
          text-align: center;
        }

        .tab-article h2 {
          font-size: 1.15rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 32px 0 12px 0;
        }

        .tab-article h2:first-of-type {
          margin-top: 24px;
        }

        .tab-article p {
          margin: 0 0 16px 0;
          font-size: 0.95rem;
        }

        .tab-article .lead {
          font-size: 1.05rem;
          color: var(--text-primary);
          margin-bottom: 24px;
        }

        .tab-article strong {
          color: var(--text-primary);
        }

        .tab-article a {
          color: var(--accent-cyan);
          text-decoration: none;
        }

        .tab-article a:hover {
          text-decoration: underline;
        }

        .user-mention {
          color: var(--accent-cyan);
          font-weight: 500;
          text-decoration: none;
        }

        .user-mention:hover {
          text-decoration: underline;
        }

        @media (max-width: 480px) {
          .tab-article h1 {
            font-size: 1.5rem;
          }

          .tab-article h2 {
            font-size: 1.1rem;
          }
        }
      `}</style>
    </article>
  );
}

function RulesTab() {
  return (
    <article className="tab-article">
      <h1>Community Rules</h1>

      <p className="lead">
        These rules help keep Makapix Club a welcoming space for everyone. Please read them
        carefully before participating.
      </p>

      <h2>Post Approval</h2>
      
      <p>
        When you post artwork, it immediately appears on your profile for anyone to see.
        However, for your post to appear site-wide—in the Recent feed, search results, and
        other public listings—it must be approved by a moderator.
      </p>

      <h2>Trust</h2>
      
      <p>
        <em>Trust</em> is a special status that moderators can grant to users. When you have
        Trust, your posts are auto-approved instantly—no waiting for moderator review. Trust
        can be granted or revoked at any time by moderators.
      </p>

      <h2 id="monitored-hashtags">Monitored Hashtags</h2>

      <p className="warning">
        The following hashtags are <strong>monitored</strong> and content using them
        is hidden by default: <code>#politics</code>, <code>#nsfw</code>,{' '}
        <code>#explicit</code>, <code>#13plus</code>, <code>#violence</code>.
      </p>

      <p>
        If you post content that falls under any of these categories, you{' '}
        <strong>must</strong> include the appropriate hashtag. Failing to tag
        monitored content is a violation that can lead to expulsion.
      </p>

      <p>
        To view content with monitored hashtags, you must explicitly enable each
        hashtag in your account settings. This applies to the web interface and
        any connected player devices.
      </p>

      <h2>User Handles</h2>
      
      <ul>
        <li>1 to 32 characters</li>
        <li>Any UTF-8 character is allowed, including emoji</li>
        <li>Leading and trailing whitespace is trimmed</li>
        <li>Must be unique (case-insensitive: &quot;Artist&quot; and &quot;artist&quot; cannot both exist)</li>
        <li>You can change your handle anytime from your profile settings</li>
      </ul>

      <h2>Reputation Tiers</h2>
      
      <p>
        Your reputation determines your upload storage quota. As you earn reputation through
        community engagement, your quota increases:
      </p>

      <div className="table-wrapper">
        <table className="tier-table">
          <thead>
            <tr>
              <th>Reputation</th>
              <th>Tier</th>
              <th>Storage Quota</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>&lt; 100</td>
              <td>Entry</td>
              <td>50 MB</td>
            </tr>
            <tr>
              <td>100 – 499</td>
              <td>Established</td>
              <td>100 MB</td>
            </tr>
            <tr>
              <td>500 – 999</td>
              <td>Senior</td>
              <td>250 MB</td>
            </tr>
            <tr>
              <td>1000+</td>
              <td>Veteran</td>
              <td>500 MB</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2>File Size Limit</h2>
      
      <p>
        Individual artworks are limited to <strong>5 MiB</strong> per file. For detailed
        information about supported formats and canvas dimensions, see the{' '}
        <Link href="/size_rules">Size Rules</Link> page.
      </p>

      <style jsx>{`
        .tab-article {
          color: var(--text-secondary);
          line-height: 1.7;
        }

        .tab-article h1 {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 24px 0;
          text-align: center;
        }

        .tab-article h2 {
          font-size: 1.15rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 32px 0 12px 0;
        }

        .tab-article h2:first-of-type {
          margin-top: 24px;
        }

        .tab-article p {
          margin: 0 0 16px 0;
          font-size: 0.95rem;
        }

        .tab-article .lead {
          font-size: 1.05rem;
          color: var(--text-primary);
          margin-bottom: 24px;
        }

        .tab-article strong {
          color: var(--text-primary);
        }

        .tab-article em {
          color: var(--accent-cyan);
          font-style: normal;
          font-weight: 500;
        }

        .tab-article ul {
          margin: 0 0 16px 0;
          padding-left: 24px;
          font-size: 0.95rem;
        }

        .tab-article li {
          margin: 8px 0;
        }

        .tab-article :global(a) {
          color: var(--accent-cyan);
          text-decoration: none;
        }

        .tab-article :global(a:hover) {
          text-decoration: underline;
        }

        .warning {
          background: rgba(255, 110, 180, 0.1);
          border-left: 3px solid var(--accent-pink);
          padding: 12px 16px;
          border-radius: 0 8px 8px 0;
        }

        .table-wrapper {
          overflow-x: auto;
          margin: 16px 0;
        }

        .tier-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.95rem;
        }

        .tier-table th,
        .tier-table td {
          padding: 12px 16px;
          text-align: left;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .tier-table th {
          background: rgba(255, 255, 255, 0.05);
          color: var(--text-primary);
          font-weight: 600;
        }

        .tier-table td {
          color: var(--text-secondary);
        }

        .tier-table tbody tr:hover {
          background: rgba(255, 255, 255, 0.03);
        }

        .tier-table tbody tr:last-child td {
          border-bottom: none;
        }

        @media (max-width: 480px) {
          .tab-article h1 {
            font-size: 1.5rem;
          }

          .tab-article h2 {
            font-size: 1.1rem;
          }

          .tier-table th,
          .tier-table td {
            padding: 10px 12px;
            font-size: 0.9rem;
          }
        }
      `}</style>
    </article>
  );
}

function ModerationTab() {
  return (
    <article className="tab-article">
      <h1>Moderation</h1>

      <p className="lead">
        Our moderators work to keep Makapix Club safe and welcoming. Here is how our
        moderation system works.
      </p>

      <h2>What Moderators Can Do</h2>
      
      <ul>
        <li>Hide or delete posts, comments, and user profiles</li>
        <li>Grant or revoke Trust status</li>
        <li>Award or remove reputation points</li>
        <li>Grant or revoke badges</li>
        <li>Request to view a user&apos;s email address (logged for audit)</li>
        <li>Ban users by email without seeing the actual address</li>
      </ul>

      <p className="note">
        All moderator actions are automatically recorded for auditing. When one moderator
        overrides another&apos;s action, it is flagged for review by the site owner.
      </p>

      <h2>Violations</h2>
      
      <p>
        If you break the community rules, moderators may issue a violation. Violations
        accumulate and lead to increasingly serious consequences:
      </p>

      <h3>First violation (warning)</h3>
      <p>
        You will be notified of the violation. No restrictions are applied, but the violation
        is recorded.
      </p>

      <h3>Second violation</h3>
      <p>
        You cannot post artworks or comments for 48 hours. After this period, your violation
        count resets.
      </p>

      <h3>Third violation</h3>
      <p>
        Your account is suspended.
      </p>

      <h2>Suspensions</h2>
      
      <p>
        A suspension temporarily prevents you from logging in. Suspension durations escalate
        with repeated offenses:
      </p>

      <ul>
        <li><strong>First suspension:</strong> 48 hours</li>
        <li><strong>Second suspension:</strong> 7 days</li>
        <li><strong>Third suspension:</strong> Permanent ban</li>
      </ul>

      <h2>Kick vs. Ban</h2>
      
      <p>
        Moderators can remove users from the platform in two ways:
      </p>

      <h3>Kick (temporary)</h3>
      <ul>
        <li>Your account is deactivated</li>
        <li>Your profile and posts remain visible to others</li>
        <li>No data is deleted</li>
        <li>Your email address is freed and can be used to create a new account</li>
      </ul>

      <h3>Ban (permanent)</h3>
      <ul>
        <li>Your account is deactivated</li>
        <li>Your profile and posts are hidden from public view</li>
        <li>Your email address is permanently blocked from creating new accounts</li>
        <li>Your data is deleted after 3 months</li>
      </ul>

      <h2>Appeals</h2>
      
      <p>
        If you believe a moderator action was unfair, or if you have concerns about moderator
        behavior, please contact the site owner{' '}
        <Link href="https://makapix.club/u/t5" className="user-mention">@Fab</Link> directly.
      </p>

      <style jsx>{`
        .tab-article {
          color: var(--text-secondary);
          line-height: 1.7;
        }

        .tab-article h1 {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 24px 0;
          text-align: center;
        }

        .tab-article h2 {
          font-size: 1.15rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 32px 0 12px 0;
        }

        .tab-article h2:first-of-type {
          margin-top: 24px;
        }

        .tab-article h3 {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-secondary);
          margin: 20px 0 8px 0;
        }

        .tab-article p {
          margin: 0 0 16px 0;
          font-size: 0.95rem;
        }

        .tab-article .lead {
          font-size: 1.05rem;
          color: var(--text-primary);
          margin-bottom: 24px;
        }

        .tab-article strong {
          color: var(--text-primary);
        }

        .tab-article ul {
          margin: 0 0 16px 0;
          padding-left: 24px;
          font-size: 0.95rem;
        }

        .tab-article li {
          margin: 8px 0;
        }

        .note {
          background: rgba(0, 212, 255, 0.1);
          border-left: 3px solid var(--accent-cyan);
          padding: 12px 16px;
          border-radius: 0 8px 8px 0;
          font-style: italic;
        }

        .user-mention {
          color: var(--accent-cyan);
          font-weight: 500;
          text-decoration: none;
        }

        .user-mention:hover {
          text-decoration: underline;
        }

        @media (max-width: 480px) {
          .tab-article h1 {
            font-size: 1.5rem;
          }

          .tab-article h2 {
            font-size: 1.1rem;
          }

          .tab-article h3 {
            font-size: 0.95rem;
          }
        }
      `}</style>
    </article>
  );
}
