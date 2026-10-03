import inspect
import database.client as c
import config.settings as s
print("FILE", c.__file__)
print("SOURCE:")
print(inspect.getsource(c.get_client))
print("---- SETTINGS URL TYPE ----")
print(type(s.settings.SUPABASE_URL))
print(s.settings.SUPABASE_URL)
print(type(s.settings.SUPABASE_ANON_KEY))
print(repr(s.settings.SUPABASE_ANON_KEY))
