import graphql
from fast_frappe.ctrl import init_frappe
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from graphql import GraphQLError

import frappe
from frappe_graphql import get_schema
from frappe_graphql.graphql import execute
from frappe_graphql.utils.resolver import default_field_resolver

app = FastAPI()


@app.get("/")
def read_root():
    init_frappe()
    available_doctypes = frappe.get_list("DocType")
    settings = frappe.get_single("System Settings")
    return {
        "available_doctypes": available_doctypes,
        "settings": settings.as_dict(),
    }


@app.on_event("startup")
def on_start():
    init_frappe()


@app.post("/graphql")
async def graphql_resolver(body: dict):
    graphql_request = frappe.parse_json(body)
    query = graphql_request.query
    variables = graphql_request.variables
    operation_name = graphql_request.operationName
    # frappe.set_user("administrator")
    output = await execute_async(query, variables, operation_name)

    if len(output.get("errors", [])):
        frappe.db.rollback()
        errors = []
        for err in output.errors:
            if isinstance(err, GraphQLError):
                err = err.formatted
            errors.append(err)
        output.errors = errors
    return output


@app.post("/graphql_sync")
def graphql_resolver_sync(body: dict):
    return execute_gql_query_sync(body)


def execute_gql_query_sync(body: dict):
    graphql_request = frappe.parse_json(body)
    query = graphql_request.query
    variables = graphql_request.variables
    operation_name = graphql_request.operationName
    output = execute(
        query=query,
        variables=variables,
        operation_name=operation_name
    )

    if len(output.get("errors", [])):
        frappe.db.rollback()
        errors = []
        for err in output.errors:
            if isinstance(err, GraphQLError):
                err = err.formatted
            errors.append(err)
        output.errors = errors
    return output


import frappe.app

app.mount('/frappe', WSGIMiddleware(frappe.app.application))


async def execute_async(query=None, variables=None, operation_name=None):
    result = await graphql.graphql(
        # is_awaitable=is_awaitable,
        schema=get_schema(),
        source=query,
        variable_values=variables,
        operation_name=operation_name,
        field_resolver=default_field_resolver,
        middleware=[frappe.get_attr(cmd) for cmd in frappe.get_hooks("graphql_middlewares")],
        context_value=frappe._dict()
    )
    output = frappe._dict()
    for k in ("data", "errors"):
        if not getattr(result, k, None):
            continue
        output[k] = getattr(result, k)
    return output

#
# def is_awaitable(x) -> bool:
#     return True
#
#
# import inspect
# import asyncio
#
#
# def isAsync(someFunc):
#     is_async_gen = inspect.isasyncgenfunction(someFunc)
#     is_coro_fn = asyncio.iscoroutinefunction(someFunc)
#     return is_async_gen or is_coro_fn
