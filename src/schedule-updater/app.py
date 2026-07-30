"""
Schedule Updater Lambda
Updates schedule resources based on DynamoDB config
Triggered by DynamoDB stream on config changes
"""
import os
import json
import boto3
from boto3.dynamodb.types import TypeDeserializer

events_client = boto3.client('events')
scheduler_client = boto3.client('scheduler')
deserializer = TypeDeserializer()

# Map day names to cron day-of-week
DAY_MAP = {
    'sunday': 'SUN',
    'monday': 'MON',
    'tuesday': 'TUE',
    'wednesday': 'WED',
    'thursday': 'THU',
    'friday': 'FRI',
    'saturday': 'SAT'
}

DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def deserialize_value(value_attribute):
    """Decode DynamoDB stream values written by boto3 resource put_item."""
    if not value_attribute:
        return {}
    value = deserializer.deserialize(value_attribute)
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(value, dict):
        return {}
    return value


def as_int(value, default=0, minimum=None, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default

    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('1', 'true', 'yes', 'y', 'enabled')


def legacy_eventbridge_utc_cron(day, hour):
    """
    Build a UTC EventBridge Rule cron for the legacy playlist schedule.

    Campaign scheduling uses EventBridge Scheduler with a real timezone.
    """
    utc_hour = (hour + 8) % 24
    return f"cron(0 {utc_hour} ? * {DAY_MAP.get(day, 'SAT')} *)", utc_hour


def pacific_scheduler_cron(day, hour):
    """Build a local-time cron for EventBridge Scheduler in America/Los_Angeles."""
    normalized_day = day if day in DAYS else 'monday'
    scheduled_hour = as_int(hour, default=0, minimum=0, maximum=23)
    return f"cron(0 {scheduled_hour} ? * {DAY_MAP[normalized_day]} *)", normalized_day, scheduled_hour


def default_campaign_time(reset_day, reset_hour):
    reset_day = reset_day if reset_day in DAYS else 'monday'
    campaign_hour = reset_hour - 2
    if campaign_hour >= 0:
        return reset_day, campaign_hour
    return DAYS[(DAYS.index(reset_day) - 1) % len(DAYS)], campaign_hour + 24


def update_rule(rule_name, cron_expression, enabled, description):
    if not rule_name:
        print(f"Skipping rule update because rule name is not configured: {description}")
        return

    try:
        events_client.put_rule(
            Name=rule_name,
            ScheduleExpression=cron_expression,
            State='ENABLED' if enabled else 'DISABLED',
            Description=description
        )
        print(f"Successfully updated rule: {rule_name}")
    except Exception as e:
        print(f"Error updating EventBridge rule {rule_name}: {e}")


def update_campaign_schedule(schedule_name, cron_expression, enabled, description):
    if not schedule_name:
        print("Skipping campaign schedule update because CAMPAIGN_SCHEDULE_NAME is not configured")
        return

    target_arn = os.environ.get('CAMPAIGN_SCHEDULE_TARGET_ARN')
    role_arn = os.environ.get('CAMPAIGN_SCHEDULE_ROLE_ARN')
    if not target_arn or not role_arn:
        print("Skipping campaign schedule update because Scheduler target env vars are incomplete")
        return

    try:
        scheduler_client.update_schedule(
            Name=schedule_name,
            FlexibleTimeWindow={'Mode': 'OFF'},
            ScheduleExpression=cron_expression,
            ScheduleExpressionTimezone='America/Los_Angeles',
            State='ENABLED' if enabled else 'DISABLED',
            Description=description,
            Target={
                'Arn': target_arn,
                'RoleArn': role_arn
            }
        )
        print(f"Successfully updated Scheduler schedule: {schedule_name}")
    except Exception as e:
        print(f"Error updating Scheduler schedule {schedule_name}: {e}")


def lambda_handler(event, context):
    """Handle DynamoDB stream events"""
    try:
        for record in event.get('Records', []):
            if record['eventName'] in ['INSERT', 'MODIFY']:
                new_image = record['dynamodb'].get('NewImage', {})

                config_key = new_image.get('configKey', {}).get('S', '')
                value = deserialize_value(new_image.get('value'))

                if config_key == 'playlist_generation':
                    day = value.get('day', 'saturday').lower()
                    hour = as_int(value.get('hour'), default=2, minimum=0, maximum=23)

                    print(f"Updating playlist schedule to: {day} at {hour}:00 SLT")

                    cron_expression, utc_hour = legacy_eventbridge_utc_cron(day, hour)
                    description = (
                        f'Generate weekly Top 10 playlist every {day.capitalize()} '
                        f'at {hour}:00 SLT ({utc_hour:02d}:00 UTC legacy rule)'
                    )
                    update_rule(
                        os.environ.get('PLAYLIST_RULE_NAME'),
                        cron_expression,
                        True,
                        description
                    )

                if config_key == 'chart_generation':
                    reset_day = value.get('day', 'monday').lower()
                    reset_hour = as_int(value.get('hour'), default=0, minimum=0, maximum=23)
                    default_campaign_day, default_campaign_hour = default_campaign_time(reset_day, reset_hour)
                    campaign_day = value.get('campaign_day', default_campaign_day).lower()
                    campaign_hour = as_int(value.get('campaign_hour'), default=default_campaign_hour, minimum=0, maximum=23)
                    campaign_enabled = as_bool(value.get('campaign_generation_enabled'), default=True)
                    freeze_enabled = as_bool(value.get('freeze_enabled'), default=True)

                    print(
                        "Updating campaign schedule: "
                        f"campaign={campaign_day} at {campaign_hour}:00 SLT; "
                        f"reset={reset_day} at {reset_hour}:00 SLT; "
                        f"freeze_enabled={freeze_enabled}; enabled={campaign_enabled}"
                    )

                    cron_expression, scheduled_day, scheduled_hour = pacific_scheduler_cron(
                        campaign_day,
                        campaign_hour
                    )
                    description = (
                        f'Generate weekly campaign draft every {scheduled_day.capitalize()} '
                        f'at {scheduled_hour:02d}:00 SLT before chart reset'
                    )
                    update_campaign_schedule(
                        os.environ.get('CAMPAIGN_SCHEDULE_NAME'),
                        cron_expression,
                        campaign_enabled,
                        description
                    )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Schedule updated'})
        }

    except Exception as e:
        print(f"Error in schedule updater: {e}")
        import traceback
        traceback.print_exc()

        # Don't fail hard - just log the error
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Processed with errors'})
        }
