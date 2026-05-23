from datetime import datetime


class AntiRollback:

    @staticmethod
    def is_time_invalid(last_run_time):

        try:
            old = datetime.fromisoformat(last_run_time)
            now = datetime.now()

            return now < old

        except:
            return False