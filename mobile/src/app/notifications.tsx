import { RecentActivity } from '@/components/recent-activity';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';

/** Notifications: every time your Circle was alerted (missed check-ins and SOS). */
export default function NotificationsScreen() {
  return (
    <Screen title="Notifications">
      <ThemedText themeColor="textSecondary">
        Alerts sent to your Circle, and whether they were told you&apos;re safe.
      </ThemedText>
      <RecentActivity filter="alerts" />
    </Screen>
  );
}
