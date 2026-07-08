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

class QueryMethodTestsMixin:
    def verify_post_query_equivalence(self, selector, limit=25, partition=None):
        body = json.dumps({
            "selector": selector,
            "limit": limit,
        })
        headers = {
            "Content-Type": "application/json",
        }
        if partition:
            path = self.db.path([f"_partition/{partition}/_find"])
        else:
            path = self.db.path("_find")
            
        post = self.db.sess.request(
            "POST",
            path,
            data=body,
            headers=headers,
        )
        query = self.db.sess.request(
            "QUERY",
            path,
            data=body,
            headers=headers,
        )
        
        post.raise_for_status()
        query.raise_for_status()
        
        self.assertEqual(post.json(), query.json())

    def test_query_method_equivalence(self):
        # 1. Simple selector
        self.verify_post_query_equivalence({"age": {"$gt": 20}})
        # 2. Nested selector
        self.verify_post_query_equivalence({"$and": [{"age": {"$gt": 20}}, {"status": "active"}]})
        # 3. In selector
        self.verify_post_query_equivalence({"age": {"$in": [25, 35]}})
        # 4. Projection
        body = json.dumps({
            "selector": {"age": {"$gt": 20}},
            "fields": ["name", "status"]
        })
        headers = {"Content-Type": "application/json"}
        post = self.db.sess.request("POST", self.db.path("_find"), data=body, headers=headers)
        query = self.db.sess.request("QUERY", self.db.path("_find"), data=body, headers=headers)
        post.raise_for_status()
        query.raise_for_status()
        self.assertEqual(post.json(), query.json())

    def test_query_method_explain_exclusion(self):
        body = json.dumps({"selector": {"age": {"$gt": 20}}})
        headers = {"Content-Type": "application/json"}
        r = self.db.sess.request("QUERY", self.db.path("_explain"), data=body, headers=headers)
        self.assertEqual(r.status_code, 405)

    def test_query_method_errors(self):
        # Malformed JSON with application/json header
        invalid_body = "{invalid_json}"
        headers = {"Content-Type": "application/json"}
        
        post = self.db.sess.request("POST", self.db.path("_find"), data=invalid_body, headers=headers)
        query = self.db.sess.request("QUERY", self.db.path("_find"), data=invalid_body, headers=headers)
        
        self.assertEqual(post.status_code, query.status_code)
        self.assertEqual(post.json().get("error"), query.json().get("error"))
        self.assertEqual(post.json().get("reason"), query.json().get("reason"))

    def test_content_type_parity(self):
        # Invalid Content-Type
        body = json.dumps({"selector": {"age": {"$gt": 20}}})
        headers = {"Content-Type": "text/plain"}
        
        post = self.db.sess.request("POST", self.db.path("_find"), data=body, headers=headers)
        query = self.db.sess.request("QUERY", self.db.path("_find"), data=body, headers=headers)
        
        self.assertEqual(post.status_code, query.status_code)
        self.assertEqual(post.json().get("error"), query.json().get("error"))
        self.assertEqual(post.json().get("reason"), query.json().get("reason"))

    def test_query_method_allowed(self):
        # GET should return 405 with "POST,QUERY" in Allow header
        r = self.db.sess.request("GET", self.db.path("_find"))
        self.assertEqual(r.status_code, 405)
        allow = r.headers.get("Allow")
        self.assertIsNotNone(allow)
        methods = {method.strip() for method in allow.split(",")}
        self.assertEqual(methods, {"POST", "QUERY"})

    def test_bookmark_pagination_parity(self):
        selector = {"age": {"$gt": 20}}
        body_p1 = json.dumps({"selector": selector, "limit": 2})
        headers = {"Content-Type": "application/json"}
        
        post_p1 = self.db.sess.request("POST", self.db.path("_find"), data=body_p1, headers=headers)
        query_p1 = self.db.sess.request("QUERY", self.db.path("_find"), data=body_p1, headers=headers)
        
        post_p1.raise_for_status()
        query_p1.raise_for_status()
        
        self.assertEqual(post_p1.json().get("docs"), query_p1.json().get("docs"))
        
        bookmark_post = post_p1.json().get("bookmark")
        bookmark_query = query_p1.json().get("bookmark")
        self.assertEqual(bookmark_post, bookmark_query)
        
        body_p2 = json.dumps({"selector": selector, "limit": 2, "bookmark": bookmark_query})
        post_p2 = self.db.sess.request("POST", self.db.path("_find"), data=body_p2, headers=headers)
        query_p2 = self.db.sess.request("QUERY", self.db.path("_find"), data=body_p2, headers=headers)
        
        post_p2.raise_for_status()
        query_p2.raise_for_status()
        
        self.assertEqual(post_p2.json().get("docs"), query_p2.json().get("docs"))


class NonPartitionedQueryMethodTests(mango.UserDocsTests, QueryMethodTestsMixin):
    pass


class PartitionedQueryMethodTests(mango.PartitionedUserDocsTests, QueryMethodTestsMixin):
    def test_partitioned_query_equivalence(self):
        # Since partitioned db has partition keys based on index, let's query partition "1"
        self.verify_post_query_equivalence({"age": {"$gt": 20}}, partition="1")
