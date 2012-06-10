def monoid():
    return dict(filters='',
                joins='',
                parameters=[],
                )


def combine_with_separator(separator, prop, acc, d):
    value = d.get(prop, None)
    if value is not None:
        if acc.get(prop):
            acc[prop] = acc[prop] + separator + value
        else:
            acc[prop] = value
    return acc


def combine_filters_and(acc, result):
    acc = combine_with_separator(' AND ', 'filters', acc, result)
    acc = combine_with_separator(', ', 'joins', acc, result)
    acc['parameters'].extend(result.get('parameters', []))
    return acc


def combine_filters_or(acc, result):
    acc = combine_with_separator(' OR ', 'filters', acc, result)
    acc = combine_with_separator(', ', 'joins', acc, result)
    acc['parameters'].extend(result.get('parameters', []))
    return acc


def equal(column, value):
    return dict(filters='%s = %%s' % column,
                parameters=[value])


def notequal(column, value):
    return dict(filters='%s != %%s' % column,
                parameters=[value])


def in_(column, values):
    if not values:
        return {}
    if isinstance(values, basestring):
        return equal(column, values)
    elif len(values) == 1:
        return equal(column, values[0])
    else:
        placeholder_string = ', '.join(['%s'] * len(values))
        return dict(filters='%s IN (%s)' % (column, placeholder_string),
                    parameters=values)


def vertical(key_column, key_value, value_column, value):
    return combine_filters_and(
        equal(key_column, key_value),
        in_(value_column, value))


def join(table, join_spec, join_type='INNER'):
    return dict(
        joins='%s JOIN %s ON %s' % (join_type, table, join_spec))


def generate_sql(spec):
    return ('SELECT cu.* FROM core_user cu %s WHERE %s' % (
            spec['joins'], spec['filters']))
