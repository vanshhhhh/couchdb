# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import json
import mango

class QueryMethodTests(mango.UserDocsTests):
    def test_query_method_equivalence(self):
        # 1. Simple selector
        selector = {"age": {"$gt": 20}}
        
        # POST response
        post_docs = self.db.find(selector)
        
        # QUERY response
        body = json.dumps({"selector": selector, "limit": 25})
        r = self.db.sess.request("QUERY", self.db.path("_find"), data=body)
        r.raise_for_status()
        query_docs = r.json()["docs"]
        
        self.assertEqual(post_docs, query_docs)

    def test_query_method_explain(self):
        selector = {"age": {"$gt": 20}}
        body = json.dumps({"selector": selector})
        # QUERY explain should return 405 Method Not Allowed since it only supports POST
        r_explain = self.db.sess.request("QUERY", self.db.path("_explain"), data=body)
        self.assertEqual(r_explain.status_code, 405)

    def test_query_method_errors(self):
        # Malformed JSON with application/json header
        r = self.db.sess.request("QUERY", self.db.path("_find"), data="{invalid_json}")
        self.assertEqual(r.status_code, 400)

    def test_query_method_allowed(self):
        # GET should return 405 with "POST,QUERY" in Allow header
        r = self.db.sess.request("GET", self.db.path("_find"))
        self.assertEqual(r.status_code, 405)
        allow = r.headers.get("Allow") or r.headers.get("allow")
        self.assertTrue("POST,QUERY" in allow or "QUERY,POST" in allow)
